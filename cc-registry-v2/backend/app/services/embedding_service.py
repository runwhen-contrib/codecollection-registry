"""
Embedding generation service using Azure OpenAI.

Generates text embeddings for vector search. Supports separate embedding
endpoint configuration via AZURE_OPENAI_EMBEDDING_* env vars, falling back
to the main AZURE_OPENAI_* credentials.
"""
import logging
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings via Azure OpenAI (or OpenAI directly)."""

    def __init__(self):
        self._client = None
        self._deployment: str = settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
        self._dimensions: int = settings.EMBEDDING_DIMENSIONS
        self._batch_size: int = settings.EMBEDDING_BATCH_SIZE
        self._init_client()

    def _init_client(self):
        endpoint = (
            settings.AZURE_OPENAI_EMBEDDING_ENDPOINT
            or settings.AZURE_OPENAI_ENDPOINT
        )
        api_key = (
            settings.AZURE_OPENAI_EMBEDDING_API_KEY
            or settings.AZURE_OPENAI_API_KEY
        )
        api_version = (
            settings.AZURE_OPENAI_EMBEDDING_API_VERSION
            or settings.AZURE_OPENAI_API_VERSION
        )

        if not endpoint or not api_key:
            logger.warning(
                "Azure OpenAI embedding credentials not configured — "
                "embedding generation will be unavailable"
            )
            return

        try:
            from openai import AzureOpenAI

            self._client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
            )
            is_dedicated = bool(settings.AZURE_OPENAI_EMBEDDING_ENDPOINT)
            label = "dedicated embedding" if is_dedicated else "shared"
            logger.info(
                f"Embedding service initialised ({label} endpoint: {endpoint})"
            )
        except Exception as e:
            logger.error(f"Failed to initialise embedding client: {e}")

    @property
    def available(self) -> bool:
        return self._client is not None

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts.

        Returns a list of embedding vectors in the same order as *texts*.
        Failed items are represented by empty lists.
        """
        if not texts:
            return []
        if not self._client:
            logger.error("Embedding client not available")
            return [[] for _ in texts]

        all_embeddings: List[List[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            try:
                response = self._client.embeddings.create(
                    input=batch, model=self._deployment
                )
                for item in response.data:
                    all_embeddings.append(item.embedding)
            except Exception as e:
                logger.error(f"Embedding batch {start // self._batch_size} failed: {e}")
                all_embeddings.extend([[] for _ in batch])

        return all_embeddings

    def embed_text(self, text: str) -> List[float]:
        """Generate a single embedding vector."""
        results = self.embed_texts([text])
        return results[0] if results else []


_instance: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _instance
    if _instance is None:
        _instance = EmbeddingService()
    return _instance
