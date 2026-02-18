/**
 * Type definitions for Elefante Grounding Extension
 */

export interface MemoryResult {
    id: string;
    title: string;
    summary: string;
    content: string;
    score: number;
    memory_type: string;
    topic: string;
}

export interface SearchOptions {
    limit?: number;
    minSimilarity?: number;
    mode?: 'semantic' | 'structured' | 'hybrid';
}

export interface SearchResponse {
    success: boolean;
    count: number;
    results: Array<{
        memory: {
            id: string;
            content: string;
            metadata: {
                score?: number;
                memory_type?: string;
                topic?: string;
                custom_metadata?: {
                    title?: string;
                    summary?: string;
                };
            };
        };
        score: number;
    }>;
}

export interface ExtensionConfig {
    enabled: boolean;
    serverUrl: string;
    minSimilarity: number;
    maxResults: number;
    cacheTtlSeconds: number;
    showNotifications: boolean;
}

export interface CacheEntry<T> {
    value: T;
    expiresAt: number;
}
