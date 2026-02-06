"""
Configuration management for Elefante memory system

Loads configuration from config.yaml with environment variable overrides.
Provides singleton access to configuration throughout the application.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, model_validator
from dotenv import load_dotenv

from src.utils.version import PACKAGE_VERSION

# Define absolute paths relative to user home directory for global persistence
# This ensures databases are shared across all workspaces
USER_HOME = Path.home()
ELEFANTE_HOME = USER_HOME / ".elefante"
DATA_DIR = ELEFANTE_HOME / "data"
CHROMA_DIR = DATA_DIR / "chroma"
KUZU_DIR = DATA_DIR / "kuzu"
LOGS_DIR = ELEFANTE_HOME / "logs"

# Ensure directories exist
ELEFANTE_HOME.mkdir(exist_ok=True)

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)
# Note: KUZU_DIR should NOT be created here - Kuzu creates its own directory structure
# KUZU_DIR.mkdir(exist_ok=True)  # Commented out - causes conflict with Kuzu 0.11+
LOGS_DIR.mkdir(exist_ok=True)


class VectorStoreConfig(BaseModel):
    """Vector store (ChromaDB) configuration"""
    type: str = "chromadb"
    persist_directory: str = str(CHROMA_DIR)
    collection_name: str = "memories"
    embedding_model: str = "thenlper/gte-base"
    embedding_dimension: int = 768
    distance_metric: str = "cosine"


class GraphStoreConfig(BaseModel):
    """Graph store (Kuzu) configuration"""
    type: str = "kuzu"
    database_path: str = str(DATA_DIR / "kuzu_db")
    buffer_pool_size: str = "512MB"
    max_num_threads: int = 4


class OrchestratorConfig(BaseModel):
    """Hybrid orchestrator configuration"""
    default_mode: str = "hybrid"
    vector_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    graph_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    max_results: int = Field(default=10, ge=1, le=100)
    min_similarity: float = Field(default=0.3, ge=0.0, le=1.0)
    
    @model_validator(mode="after")
    def validate_weights(self):
        total = self.vector_weight + self.graph_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError("vector_weight + graph_weight must equal 1.0")
        return self


class MCPServerConfig(BaseModel):
    """MCP server configuration"""
    name: str = "elefante"
    version: str = PACKAGE_VERSION
    description: str = "Local AI Memory System with Vector and Graph Storage"
    port: Optional[int] = None
    host: Optional[str] = None


class EmbeddingsConfig(BaseModel):
    """Embedding service configuration"""
    provider: str = "sentence-transformers"
    model: str = "thenlper/gte-base"
    device: str = "cpu"
    batch_size: int = Field(default=32, ge=1, le=128)
    normalize: bool = True


class LLMConfig(BaseModel):
    """LLM service configuration"""
    # NOTE: Elefante does not connect to an LLM. This section is kept for legacy
    # config compatibility, but is not used by runtime.
    provider: str = "agent-managed"
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 0
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = "INFO"
    format: str = "json"
    file: str = str(LOGS_DIR / "elefante.log")
    max_size: str = "10MB"
    backup_count: int = 5
    console: bool = True


class MemoryConfig(BaseModel):
    """Memory management configuration"""
    auto_consolidate: bool = False
    consolidation_threshold: int = 1000
    importance_decay: bool = False
    max_age_days: int = Field(default=365, ge=0)


class ConsolidationConfig(BaseModel):
    """Consolidation job configuration"""
    enabled: bool = False
    interval_hours: int = Field(default=24, ge=1)
    strength_threshold: float = Field(default=0.1, ge=0.0, le=1.0)
    archive_threshold_days: int = Field(default=180, ge=0)


class TemporalDecayConfig(BaseModel):
    """Temporal memory decay & reinforcement configuration"""
    enabled: bool = True
    default_decay_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    default_reinforcement_factor: float = Field(default=0.1, ge=0.0, le=1.0)
    semantic_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    temporal_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    consolidation: ConsolidationConfig = Field(default_factory=ConsolidationConfig)
    
    @model_validator(mode="after")
    def validate_weights(self):
        total = self.semantic_weight + self.temporal_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError("semantic_weight + temporal_weight must equal 1.0")
        return self


class PerformanceConfig(BaseModel):
    """Performance tuning configuration"""
    cache_embeddings: bool = True
    cache_size: int = Field(default=1000, ge=0)
    parallel_queries: bool = True
    query_timeout: int = Field(default=30, ge=1)


class FeaturesConfig(BaseModel):
    """Feature flags"""
    enable_graph_store: bool = True
    enable_vector_store: bool = True
    enable_auto_tagging: bool = False
    enable_deduplication: bool = True


class ElefanteModeConfig(BaseModel):
    """Elefante Mode configuration (v1.1.0) - Transaction-Scoped Locking"""
    enabled: bool = True  # v1.1.0: Always enabled (transaction-scoped locking)
    lock_timeout_seconds: int = Field(default=5, ge=1, le=30)
    cleanup_on_disable: bool = True


class UserProfileConfig(BaseModel):
    """User profile configuration"""
    user_name: str = "User"
    user_id: str = "user_default"
    auto_link_first_person: bool = True
    detect_code_blocks: bool = True


class ElefanteConfig(BaseModel):
    """Main Elefante configuration"""
    version: str = PACKAGE_VERSION
    data_dir: str = str(DATA_DIR)
    anonymized_telemetry: bool = False
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    graph_store: GraphStoreConfig = Field(default_factory=GraphStoreConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    mcp_server: MCPServerConfig = Field(default_factory=MCPServerConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    user_profile: UserProfileConfig = Field(default_factory=UserProfileConfig)
    temporal_decay: TemporalDecayConfig = Field(default_factory=TemporalDecayConfig)
    elefante_mode: ElefanteModeConfig = Field(default_factory=ElefanteModeConfig)


class Config:
    """
    Configuration manager for Elefante
    
    Loads configuration from config.yaml and applies environment variable overrides.
    Provides singleton access to configuration.
    """
    
    _instance: Optional['Config'] = None
    _config: Optional[ElefanteConfig] = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize configuration if not already loaded"""
        if self._config is None:
            self.load()
    
    def load(self, config_path: Optional[str] = None) -> None:
        """
        Load configuration from file and environment variables
        
        Args:
            config_path: Path to config.yaml (default: ./config.yaml)
        """
        # Load environment variables from .env file
        load_dotenv()
        
        # Determine config file path
        if config_path is None:
            config_path = os.getenv('ELEFANTE_CONFIG_PATH', 'config.yaml')
        
        config_file = Path(config_path)
        
        # Load YAML configuration
        if config_file.exists():
            with open(config_file, 'r') as f:
                config_dict = yaml.safe_load(f)
                # Extract elefante section if it exists
                if 'elefante' in config_dict:
                    config_dict = config_dict['elefante']
        else:
            # Use default configuration
            config_dict = {}
        
        # Apply environment variable overrides
        config_dict = self._apply_env_overrides(config_dict)

        # Normalize derived storage paths (so data_dir drives defaults)
        config_dict = self._normalize_storage_paths(config_dict)
        
        # Validate and create configuration object
        self._config = ElefanteConfig(**config_dict)

        # Ensure runtime directories exist for the active configuration
        self._ensure_runtime_directories()

    def _normalize_storage_paths(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Derive vector/graph storage paths from elefante.data_dir when unset.

        This keeps `ELEFANTE_DATA_DIR` and/or `config.yaml` consistent with
        ChromaDB and Kuzu default locations.
        """
        data_dir = config_dict.get('data_dir')
        if not data_dir:
            return config_dict

        data_dir_path = Path(str(data_dir))

        vector_store = config_dict.get('vector_store') or {}
        if 'persist_directory' not in vector_store:
            vector_store['persist_directory'] = str(data_dir_path / 'chroma')
        config_dict['vector_store'] = vector_store

        graph_store = config_dict.get('graph_store') or {}
        if 'database_path' not in graph_store:
            graph_store['database_path'] = str(data_dir_path / 'kuzu_db')
        config_dict['graph_store'] = graph_store

        return config_dict

    def _ensure_runtime_directories(self) -> None:
        """Create configured directories that should exist at runtime."""
        if self._config is None:
            return

        # Data dir and Chroma dir are safe to create. Kuzu DB directory should
        # not be pre-created (Kuzu manages the DB directory itself).
        data_dir = Path(self._config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        chroma_dir = Path(self._config.vector_store.persist_directory)
        chroma_dir.mkdir(parents=True, exist_ok=True)
    
    def _apply_env_overrides(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environment variable overrides to configuration
        
        Environment variables follow the pattern: ELEFANTE_<SECTION>_<KEY>
        Example: ELEFANTE_DATA_DIR, ELEFANTE_LOGGING_LEVEL
        """
        # Data directory override
        if data_dir := os.getenv('ELEFANTE_DATA_DIR'):
            config_dict['data_dir'] = data_dir
        
        # Logging level override
        if log_level := os.getenv('ELEFANTE_LOG_LEVEL'):
            if 'logging' not in config_dict:
                config_dict['logging'] = {}
            config_dict['logging']['level'] = log_level
        
        # Embedding model override
        if embedding_model := os.getenv('ELEFANTE_EMBEDDING_MODEL'):
            if 'embeddings' not in config_dict:
                config_dict['embeddings'] = {}
            config_dict['embeddings']['model'] = embedding_model
        
        # Device override
        if device := os.getenv('ELEFANTE_DEVICE'):
            if 'embeddings' not in config_dict:
                config_dict['embeddings'] = {}
            config_dict['embeddings']['device'] = device
        
        # MCP port override
        if mcp_port := os.getenv('ELEFANTE_MCP_PORT'):
            if 'mcp_server' not in config_dict:
                config_dict['mcp_server'] = {}
            config_dict['mcp_server']['port'] = int(mcp_port)
        
        # Elefante Mode override (ELEFANTE_MODE=Y or ELEFANTE_MODE=N)
        if elefante_mode := os.getenv('ELEFANTE_MODE'):
            if 'elefante_mode' not in config_dict:
                config_dict['elefante_mode'] = {}
            config_dict['elefante_mode']['enabled'] = elefante_mode.upper() in ('Y', 'YES', 'TRUE', '1', 'ON')
        
        # NOTE: Elefante does not make direct LLM calls; no LLM/OpenAI env overrides are applied here.
        # Any LLM connectivity must live in the calling agent, which passes enriched fields into tools.
        
        return config_dict
    
    @property
    def elefante(self) -> ElefanteConfig:
        """Get Elefante configuration"""
        if self._config is None:
            self.load()
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key
        
        Args:
            key: Configuration key in dot notation (e.g., 'vector_store.collection_name')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        if self._config is None:
            self.load()
        
        # Split key by dots and traverse config
        parts = key.split('.')
        value = self._config
        
        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            else:
                return default
        
        return value
    
    def reload(self, config_path: Optional[str] = None) -> None:
        """
        Reload configuration from file
        
        Args:
            config_path: Path to config.yaml
        """
        self._config = None
        self.load(config_path)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        if self._config is None:
            self.load()
        return self._config.model_dump()
    
    def __repr__(self) -> str:
        return f"Config(version={self.elefante.version}, data_dir={self.elefante.data_dir})"


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance
    
    Returns:
        Config: Global configuration instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reload_config(config_path: Optional[str] = None) -> Config:
    """
    Reload global configuration
    
    Args:
        config_path: Path to config.yaml
        
    Returns:
        Config: Reloaded configuration instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    _config_instance.reload(config_path)
    return _config_instance

