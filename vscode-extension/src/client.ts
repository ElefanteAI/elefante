/**
 * Elefante MCP Server Client
 * 
 * Communicates with the Elefante MCP server to search memories.
 * Uses HTTP/JSON-RPC to invoke the elefanteMemorySearch tool.
 */

import { MemoryResult, SearchOptions, SearchResponse } from './types';
import { logInfo, logError, logDebug, logWarn } from './logger';

export class ElefanteClient {
    private serverUrl: string;
    private timeout: number;

    constructor(serverUrl: string = 'http://localhost:8000', timeoutMs: number = 2000) {
        this.serverUrl = serverUrl;
        this.timeout = timeoutMs;
    }

    /**
     * Update server URL (for config changes)
     */
    setServerUrl(url: string): void {
        this.serverUrl = url;
    }

    /**
     * Check if the Elefante server is available
     */
    async isServerAvailable(): Promise<boolean> {
        try {
            // Try to hit a simple endpoint or just check TCP connection
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.timeout);

            const response = await fetch(`${this.serverUrl}/health`, {
                method: 'GET',
                signal: controller.signal,
            });

            clearTimeout(timeoutId);
            return response.ok;
        } catch (error) {
            // Server might not have /health endpoint, try MCP handshake
            // For now, we'll just return false and handle gracefully
            logDebug('Health check failed, server may be unavailable');
            return false;
        }
    }

    /**
     * Search Elefante memories using the MCP tool
     * 
     * This calls the elefanteMemorySearch tool via HTTP.
     * The MCP server exposes tools at a REST-like endpoint.
     */
    async search(query: string, options: SearchOptions = {}): Promise<MemoryResult[]> {
        const {
            limit = 5,
            minSimilarity = 0.5,
            mode = 'hybrid',
        } = options;

        logDebug(`Searching Elefante: "${query.substring(0, 50)}..." (limit=${limit}, min=${minSimilarity})`);

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.timeout);

            // Call the dashboard API search endpoint
            // The dashboard server runs on port 8000 by default
            const url = new URL(`${this.serverUrl}/api/search`);
            url.searchParams.set('query', query);
            url.searchParams.set('limit', String(limit));
            url.searchParams.set('min_similarity', String(minSimilarity));

            const response = await fetch(url.toString(), {
                method: 'GET',
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }

            const data = await response.json() as SearchResponse;

            if (!data.success) {
                logWarn('Search returned success=false');
                return [];
            }

            // Transform response to MemoryResult[]
            const results: MemoryResult[] = data.results
                .filter(r => r.score >= minSimilarity)
                .map(r => ({
                    id: r.memory.id,
                    title: r.memory.metadata.custom_metadata?.title || `Memory ${r.memory.id.substring(0, 8)}`,
                    summary: r.memory.metadata.custom_metadata?.summary || r.memory.content.substring(0, 200),
                    content: r.memory.content,
                    score: r.score,
                    memory_type: r.memory.metadata.memory_type || 'fact',
                    topic: r.memory.metadata.topic || 'general',
                    knowledge_type: r.memory.metadata.knowledge_type || 'fact',
                }));

            logInfo(`Found ${results.length} relevant memories`);
            return results;

        } catch (error) {
            if (error instanceof Error) {
                if (error.name === 'AbortError') {
                    logWarn(`Search timed out after ${this.timeout}ms`);
                } else {
                    logError('Search failed', error);
                }
            }
            return [];
        }
    }

    /**
     * Alternative: Search using stdio MCP protocol
     * This would be used if we spawn the MCP server as a subprocess
     */
    async searchViaStdio(query: string, options: SearchOptions = {}): Promise<MemoryResult[]> {
        // TODO: Implement if HTTP approach doesn't work
        // This would involve:
        // 1. Spawning the MCP server process
        // 2. Sending JSON-RPC messages via stdin
        // 3. Reading responses from stdout
        logWarn('stdio search not yet implemented');
        return [];
    }
}
