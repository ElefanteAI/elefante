# Elefante Grounding Extension

Automatically injects relevant memories from Elefante into AI chat context.

## The Problem

AI agents "forget" to check your memory system. Even with explicit instructions, they often skip the search and answer from their training data instead of your stored preferences and decisions.

## The Solution

This extension **structurally enforces** memory retrieval by:

1. Intercepting every chat message before it reaches the AI
2. Searching Elefante for semantically relevant memories
3. Injecting found memories directly into the prompt context
4. The AI then sees your memories alongside your question

**The AI cannot ignore what's already in its prompt.**

## Installation

### Prerequisites

- VS Code 1.85.0 or later
- Elefante dashboard server running (`python -m src.dashboard.server`)
- GitHub Copilot Chat extension

### Install from Source

```bash
cd vscode-extension
npm install
npm run compile
```

Then press F5 in VS Code to launch a development instance with the extension loaded.

### Install from VSIX (Coming Soon)

```bash
code --install-extension elefante-grounding-0.1.0.vsix
```

## Usage

### Automatic Grounding

Once installed and configured, the extension automatically searches Elefante for every chat message. Relevant memories are injected into the context.

### Manual Invocation

Type `@elefante` in the chat to explicitly invoke the Elefante participant:

```
@elefante What are my coding preferences?
```

### Commands

- **Elefante: Toggle Grounding** - Enable/disable automatic grounding
- **Elefante: Clear Memory Cache** - Clear the search result cache
- **Elefante: Test Server Connection** - Verify Elefante server is reachable

## Configuration

| Setting | Default | Description |
| ------- | ------- | ----------- |
| `elefante.grounding.enabled` | `true` | Enable automatic memory grounding |
| `elefante.grounding.serverUrl` | `http://localhost:8000` | Elefante dashboard server URL |
| `elefante.grounding.minSimilarity` | `0.5` | Minimum similarity score (0-1) |
| `elefante.grounding.maxResults` | `5` | Maximum memories to inject |
| `elefante.grounding.cacheTtlSeconds` | `300` | Cache duration (seconds) |
| `elefante.grounding.showNotifications` | `false` | Show notification on injection |

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ You type: "How should I format Python code?"                │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Extension: Search Elefante with query                       │
│ → Returns: "[PREF] Python :: Black Formatter"               │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Extension: Inject context into prompt                       │
│                                                             │
│ [ELEFANTE MEMORY CONTEXT]                                   │
│ • [PREF] Python :: Black Formatter [preference, topic: dev] │
│   Use Black for Python formatting with line-length 100      │
│ [END ELEFANTE CONTEXT]                                      │
│                                                             │
│ User: How should I format Python code?                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ AI sees BOTH the context AND your question                  │
│ → Responds with YOUR preferences, not generic advice        │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### "Cannot reach Elefante server"

1. Ensure the Elefante dashboard server is running: `python -m src.dashboard.server`
2. Check the server URL in settings matches your setup (default: http://localhost:8000)
3. Run `Elefante: Test Server Connection` command

### No memories being injected

1. Check that grounding is enabled (run `Elefante: Toggle Grounding`)
2. Lower the `minSimilarity` threshold if memories exist but aren't matching
3. Check the Output panel (Elefante Grounding) for debug logs

### Memories seem outdated

Run `Elefante: Clear Memory Cache` to force fresh searches.

## Development

```bash
# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Watch mode
npm run watch

# Run tests
npm test

# Package extension
npx vsce package
```

## Architecture

```
src/
├── extension.ts   # VS Code activation, chat participant registration
├── grounding.ts   # Core grounding logic, orchestrates search + format
├── client.ts      # HTTP client for Elefante MCP server
├── cache.ts       # In-memory cache with TTL
├── formatter.ts   # Formats memories into context strings
├── config.ts      # Configuration management
├── logger.ts      # Logging utilities
└── types.ts       # TypeScript type definitions
```

## License

MIT - Same as Elefante main project
