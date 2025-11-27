# 📁 Elefante Project Structure

This document describes the organization of the Elefante codebase.

## Root Directory

```
Elefante/
├── .env.example          # Environment variables template
├── .gitignore           # Git ignore rules
├── config.yaml          # Default configuration
├── CONTRIBUTING.md      # Contribution guidelines
├── LICENSE              # MIT License
├── PROJECT_STRUCTURE.md # This file
├── QUICK_START.md       # Quick start guide
├── README.md            # Main documentation
├── requirements.txt     # Python dependencies
└── setup.py            # Package installation script
```

## Source Code (`src/`)

### Core Modules (`src/core/`)
- `embeddings.py` - Sentence transformer embeddings service
- `vector_store.py` - ChromaDB vector database integration
- `graph_store.py` - Kuzu graph database integration
- `orchestrator.py` - Hybrid query orchestration layer
- `__init__.py` - Core module exports

### Data Models (`src/models/`)
- `memory.py` - Memory data structures
- `entity.py` - Entity and relationship models
- `query.py` - Query models and enums
- `__init__.py` - Model exports

### MCP Server (`src/mcp/`)
- `server.py` - MCP protocol server implementation
- `__init__.py` - MCP module exports

### Utilities (`src/utils/`)
- `config.py` - Configuration management
- `logger.py` - Structured logging
- `validators.py` - Input validation
- `__init__.py` - Utility exports

## Scripts (`scripts/`)

Utility scripts for system management:

- `init_databases.py` - Initialize ChromaDB and Kuzu databases
- `health_check.py` - System health diagnostics
- `test_end_to_end.py` - End-to-end integration tests

## Setup Scripts (`setup/`)

Installation and configuration scripts:

- `configure_vscode_bob.py` - Auto-configure VSCode/Bob
- `configure_claude_desktop.py` - Auto-configure Claude Desktop
- `SETUP_VSCODE_BOB.bat` - One-click VSCode/Bob setup
- `SETUP_FOR_IDE.bat` - General IDE setup
- `start_mcp_server.bat` - Start MCP server manually
- `deploy.bat` / `deploy.sh` - Deployment automation

## Examples (`examples/`)

Example usage scripts:

- `test_real_memories.py` - Real-world memory test
- `store_user_preferences.py` - Store user preferences

## Documentation (`docs/`)

Comprehensive documentation:

- `ARCHITECTURE.md` - System architecture and design
- `DEPLOYMENT_GUIDE.md` - Production deployment guide
- `GITHUB_SETUP.md` - GitHub repository setup
- `IDE_INTEGRATION_GUIDE.md` - IDE integration details
- `IMPLEMENTATION_PLAN.md` - Implementation roadmap
- `PROJECT_STATUS.md` - Current project status
- `VSCODE_BOB_SETUP.md` - VSCode/Bob specific setup

## Data Directories (Not in Git)

These directories are created at runtime and excluded from version control:

- `data/` - Database storage
  - `data/chroma/` - ChromaDB vector store
  - `data/kuzu/` - Kuzu graph database
- `logs/` - Application logs
- `.venv/` - Python virtual environment

## Key Files

### Configuration
- `.env.example` - Template for environment variables
- `config.yaml` - Default system configuration

### Python Package
- `setup.py` - Package metadata and installation
- `requirements.txt` - Python dependencies

### Documentation
- `README.md` - Main project documentation
- `QUICK_START.md` - Quick start guide
- `CONTRIBUTING.md` - Contribution guidelines
- `LICENSE` - MIT License

## File Organization Principles

1. **Clean Root**: Only essential files in root directory
2. **Logical Grouping**: Related files in dedicated folders
3. **Clear Naming**: Self-explanatory file and folder names
4. **Documentation**: Comprehensive docs in `docs/` folder
5. **Examples Separate**: Example code in `examples/` folder
6. **Setup Isolated**: Setup scripts in `setup/` folder

## Adding New Files

When adding new files, follow these guidelines:

- **Source code** → `src/` (in appropriate subdirectory)
- **Scripts** → `scripts/` (for system utilities)
- **Examples** → `examples/` (for usage examples)
- **Documentation** → `docs/` (for detailed docs)
- **Setup/Config** → `setup/` (for installation scripts)

## Excluded from Git

The following are automatically excluded via `.gitignore`:

- Python cache (`__pycache__/`, `*.pyc`)
- Virtual environments (`.venv/`, `venv/`)
- Data directories (`data/`, `logs/`)
- IDE files (`.vscode/`, `.idea/`)
- Environment files (`.env`)
- Build artifacts (`build/`, `dist/`, `*.egg-info/`)

---

**Maintained by**: Jaime Subiabre Cisterna
**Last Updated**: 2024-11-25