"""Embedding service for Elefante memory system.

ARCHITECTURE RULE:
Elefante must not make external AI API calls. Embeddings are therefore generated
locally using Sentence Transformers.
"""

import asyncio
from typing import List, Optional, Dict, Any
from functools import lru_cache
import numpy as np

from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings
    
    Supports:
    - Sentence Transformers (local)
    """
    
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize embedding service
        
        Args:
            provider: Embedding provider (must be "sentence-transformers")
            model: Model name (provider-specific)
        """
        self.config = get_config()
        self.provider = provider or self.config.elefante.embeddings.provider
        self.model_name = model or self.config.elefante.embeddings.model
        self.device = self.config.elefante.embeddings.device
        self.batch_size = self.config.elefante.embeddings.batch_size
        self.normalize = self.config.elefante.embeddings.normalize
        
        self._model = None
        self._dimension = None
        
        logger.info(
            "initializing_embedding_service",
            provider=self.provider,
            model=self.model_name,
            device=self.device
        )
    
    def _load_model(self):
        """Load the embedding model (lazy loading)"""
        if self._model is not None:
            return
        
        if self.provider != "sentence-transformers":
            raise ValueError(
                f"Unsupported embedding provider: {self.provider}. "
                "Elefante is local-only; use provider='sentence-transformers'."
            )

        self._load_sentence_transformer()
    
    def _load_sentence_transformer(self):
        """Load Sentence Transformer model"""
        try:
            from sentence_transformers import SentenceTransformer
            
            import sys
            from contextlib import redirect_stdout
            
            logger.info("loading_sentence_transformer", model=self.model_name)
            # LAW #6: STDOUT PURITY - Redirect 3rd party library prints to stderr
            with redirect_stdout(sys.stderr):
                self._model = SentenceTransformer(self.model_name, device=self.device)
            self._dimension = self._model.get_sentence_embedding_dimension()
            
            logger.info(
                "sentence_transformer_loaded",
                model=self.model_name,
                dimension=self._dimension
            )
        except ImportError:
            logger.error("sentence_transformers_not_installed")
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            logger.error("failed_to_load_model", error=str(e))
            raise
    
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        embeddings = await self.generate_embeddings_batch([text])
        return embeddings[0]
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Ensure model is loaded
        self._load_model()
        
        logger.debug("generating_embeddings", count=len(texts))
        
        if self.provider != "sentence-transformers":
            raise ValueError(
                f"Unsupported embedding provider: {self.provider}. "
                "Elefante is local-only; use provider='sentence-transformers'."
            )

        embeddings = await self._generate_sentence_transformer_batch(texts)
        
        logger.debug("embeddings_generated", count=len(embeddings))
        return embeddings
    
    async def _generate_sentence_transformer_batch(
        self, texts: List[str]
    ) -> List[List[float]]:
        """Generate embeddings using Sentence Transformers"""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        def _encode():
            embeddings = self._model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                normalize_embeddings=self.normalize,
                convert_to_numpy=True
            )
            return embeddings.tolist()
        
        embeddings = await loop.run_in_executor(None, _encode)
        return embeddings
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this service
        
        Returns:
            Embedding dimension
        """
        if self._dimension is None:
            self._load_model()
        return self._dimension
    
    @lru_cache(maxsize=1000)
    def _cached_embedding(self, text: str) -> tuple:
        """
        Cached embedding generation (synchronous)
        
        Note: Returns tuple for hashability in lru_cache
        """
        # This is a synchronous wrapper for caching
        # In practice, use async version for new embeddings
        embeddings = asyncio.run(self.generate_embedding(text))
        return tuple(embeddings)
    
    def clear_cache(self):
        """Clear the embedding cache"""
        self._cached_embedding.cache_clear()
        logger.info("embedding_cache_cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics"""
        info = self._cached_embedding.cache_info()
        return {
            "hits": info.hits,
            "misses": info.misses,
            "size": info.currsize,
            "max_size": info.maxsize
        }
    
    async def compute_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """
        Compute cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    
    def __repr__(self) -> str:
        return f"EmbeddingService(provider={self.provider}, model={self.model_name})"


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Get global embedding service instance
    
    Returns:
        EmbeddingService: Global embedding service
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def reset_embedding_service():
    """Reset global embedding service (useful for testing)"""
    global _embedding_service
    _embedding_service = None

