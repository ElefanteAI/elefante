/**
 * Context Formatter
 * 
 * Formats memory results into a context string that will be
 * injected into the AI prompt.
 */

import { MemoryResult } from './types';

export class ContextFormatter {
    /**
     * Format memories into a context block for injection
     * 
     * Design decisions:
     * - Use clear delimiters so the AI knows where context starts/ends
     * - Include title, score, and summary (not full content to save tokens)
     * - Order by score (most relevant first)
     * - Keep it concise but informative
     */
    format(memories: MemoryResult[]): string {
        if (memories.length === 0) {
            return '';
        }

        // Sort by score descending (most relevant first)
        const sorted = [...memories].sort((a, b) => b.score - a.score);

        const lines: string[] = [
            '[ELEFANTE MEMORY CONTEXT]',
            'The following memories from your knowledge base are relevant to this conversation:',
            '',
        ];

        for (const memory of sorted) {
            // Format: • Title (type, topic): Summary
            const typeInfo = memory.memory_type || 'general';
            const topicInfo = memory.topic || 'general';
            
            lines.push(`• ${memory.title} [${typeInfo}, topic: ${topicInfo}]`);
            lines.push(`  ${memory.summary}`);
            lines.push('');
        }

        lines.push('[END ELEFANTE CONTEXT]');
        lines.push('');

        return lines.join('\n');
    }

    /**
     * Format a single memory for detailed view
     */
    formatSingle(memory: MemoryResult): string {
        return [
            `**${memory.title}**`,
            `Type: ${memory.memory_type}`,
            `Topic: ${memory.topic}`,
            `Relevance Score: ${(memory.score * 100).toFixed(1)}%`,
            '',
            memory.summary,
        ].join('\n');
    }

    /**
     * Format memories for a compact notification
     */
    formatNotification(memories: MemoryResult[]): string {
        if (memories.length === 0) {
            return 'No relevant memories found';
        }

        if (memories.length === 1) {
            return `Injected: ${memories[0].title}`;
        }

        return `Injected ${memories.length} memories: ${memories.map(m => m.title).join(', ')}`;
    }
}
