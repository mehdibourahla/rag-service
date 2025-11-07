"""Embedding generation using OpenAI."""

import logging
from typing import List

from openai import OpenAI

from src.core.config import settings
from src.models.schemas import TextChunk

logger = logging.getLogger(__name__)


class Embedder:
    """Generates embeddings for text chunks using OpenAI."""

    def __init__(self, model_name: str = None):
        """
        Initialize embedder.

        Args:
            model_name: OpenAI embedding model name (defaults to config)
        """
        self.model_name = model_name or settings.embedding_model
        self._client = None

    def _get_client(self) -> OpenAI:
        """Lazy load the OpenAI client."""
        if self._client is None:
            logger.info(f"Initializing OpenAI client with model: {self.model_name}")
            self._client = OpenAI(api_key=settings.openai_api_key)
            logger.info("OpenAI client initialized successfully")
        return self._client

    def embed_chunks(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """
        Generate embeddings for chunks.

        Args:
            chunks: List of TextChunk objects

        Returns:
            Same chunks with embeddings populated
        """
        if not chunks:
            return chunks

        client = self._get_client()

        # Extract texts
        texts = [chunk.text for chunk in chunks]

        logger.info(f"Generating embeddings for {len(texts)} chunks using {self.model_name}")

        # Generate embeddings in batches (OpenAI allows up to 2048 inputs per request)
        batch_size = 2048
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = client.embeddings.create(input=batch, model=self.model_name)
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        # Attach embeddings to chunks
        for chunk, embedding in zip(chunks, all_embeddings):
            chunk.embedding = embedding

        logger.info(f"Generated {len(all_embeddings)} embeddings")
        return chunks

    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a query.

        Args:
            query: Query text

        Returns:
            Query embedding vector
        """
        client = self._get_client()

        logger.info(f"Generating query embedding using {self.model_name}")

        # Generate query embedding
        response = client.embeddings.create(input=[query], model=self.model_name)
        embedding = response.data[0].embedding

        return embedding
