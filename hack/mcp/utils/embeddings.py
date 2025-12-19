"""
Embedding generation utilities using Azure OpenAI or local models.
"""
import os
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation"""
    provider: str = "azure"  # "azure" or "local"
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    batch_size: int = 100


class EmbeddingGenerator:
    """
    Generate embeddings using Azure OpenAI or local sentence-transformers.
    
    Supports:
    - Azure OpenAI text-embedding-3-small (default, 1536 dimensions)
    - Local sentence-transformers (384 dimensions, no API cost)
    """
    
    def __init__(self, config: EmbeddingConfig = None):
        self.config = config or EmbeddingConfig()
        self._client = None
        self._local_model = None
        
        # Try to initialize based on config
        if self.config.provider == "azure":
            self._init_azure()
        else:
            self._init_local()
    
    def _init_azure(self):
        """Initialize Azure OpenAI client"""
        try:
            from openai import AzureOpenAI
            
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            
            if endpoint and api_key:
                self._client = AzureOpenAI(
                    azure_endpoint=endpoint,
                    api_key=api_key,
                    api_version=api_version
                )
                logger.info(f"Azure OpenAI embedding client initialized")
            else:
                logger.warning("Azure OpenAI credentials not found, falling back to local")
                self._init_local()
        except ImportError:
            logger.warning("openai package not available, falling back to local")
            self._init_local()
    
    def _init_local(self):
        """Initialize local sentence-transformers model"""
        try:
            from sentence_transformers import SentenceTransformer
            
            # Use a small, fast model
            model_name = "all-MiniLM-L6-v2"
            self._local_model = SentenceTransformer(model_name)
            self.config.dimensions = 384  # This model produces 384-dim vectors
            self.config.provider = "local"
            logger.info(f"Local embedding model initialized: {model_name}")
        except ImportError:
            logger.error("sentence-transformers not available. Install with: pip install sentence-transformers")
            raise RuntimeError("No embedding provider available")
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        if self._client:
            return self._embed_azure(texts)
        elif self._local_model:
            return self._embed_local(texts)
        else:
            raise RuntimeError("No embedding provider initialized")
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []
    
    def _embed_azure(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Azure OpenAI"""
        embeddings = []
        
        # Get the embedding deployment name
        # Common names: text-embedding-3-small, text-embedding-ada-002
        deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
        
        # Process in batches
        batch_size = self.config.batch_size
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = self._client.embeddings.create(
                    input=batch,
                    model=deployment
                )
                
                for item in response.data:
                    embeddings.append(item.embedding)
                
                logger.debug(f"Embedded batch {i//batch_size + 1}")
            except Exception as e:
                logger.error(f"Azure embedding error: {e}")
                # Return empty embeddings for failed batch
                embeddings.extend([[] for _ in batch])
        
        return embeddings
    
    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local model"""
        try:
            # sentence-transformers handles batching internally
            embeddings = self._local_model.encode(
                texts,
                show_progress_bar=len(texts) > 10,
                convert_to_numpy=True
            )
            
            # Convert numpy arrays to lists
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Local embedding error: {e}")
            return [[] for _ in texts]
    
    @property
    def is_available(self) -> bool:
        """Check if embedding generation is available"""
        return self._client is not None or self._local_model is not None
    
    @property
    def provider_name(self) -> str:
        """Get the name of the current provider"""
        if self._client:
            return "Azure OpenAI"
        elif self._local_model:
            return "Local (sentence-transformers)"
        return "None"


def get_embedding_generator(prefer_local: bool = False) -> EmbeddingGenerator:
    """
    Get an embedding generator with automatic fallback.
    
    Args:
        prefer_local: If True, prefer local model even if Azure is available
        
    Returns:
        Configured EmbeddingGenerator
    """
    config = EmbeddingConfig()
    
    if prefer_local:
        config.provider = "local"
    else:
        # Check if Azure credentials are available
        if os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY"):
            config.provider = "azure"
        else:
            config.provider = "local"
    
    return EmbeddingGenerator(config)

