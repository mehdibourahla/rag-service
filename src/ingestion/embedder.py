"""Embedding generation using OpenAI with Redis caching."""

import logging
from typing import List

from openai import OpenAI

from src.core.config import settings
from src.models.schemas import TextChunk
from src.services.cache_service import get_cache_service

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
        self.cache = get_cache_service()

    def _get_client(self) -> OpenAI:
        """Lazy load the OpenAI client."""
        if self._client is None:
            logger.info(f"Initializing OpenAI client with model: {self.model_name}")
            self._client = OpenAI(api_key=settings.openai_api_key)
            logger.info("OpenAI client initialized successfully")
        return self._client

    def embed_chunks(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """
        Generate embeddings for chunks with caching.

        Args:
            chunks: List of TextChunk objects

        Returns:
            Same chunks with embeddings populated
        """
        if not chunks:
            return chunks

        client = self._get_client()

        # Extract texts and check cache
        texts_to_embed = []
        text_indices = []
        all_embeddings = [None] * len(chunks)
        cache_hits = 0

        for idx, chunk in enumerate(chunks):
            cached_embedding = self.cache.get_embedding(chunk.text, self.model_name)
            if cached_embedding:
                all_embeddings[idx] = cached_embedding
                cache_hits += 1
            else:
                texts_to_embed.append(chunk.text)
                text_indices.append(idx)

        logger.info(
            f"Embedding cache: {cache_hits} hits, {len(texts_to_embed)} misses "
            f"({cache_hits / len(chunks) * 100:.1f}% hit rate)"
        )

        # Generate embeddings for cache misses
        if texts_to_embed:
            logger.info(f"Generating {len(texts_to_embed)} embeddings using {self.model_name}")

            # Generate embeddings in batches (OpenAI allows up to 2048 inputs per request)
            batch_size = 2048
            new_embeddings = []

            for i in range(0, len(texts_to_embed), batch_size):
                batch = texts_to_embed[i : i + batch_size]
                response = client.embeddings.create(input=batch, model=self.model_name)
                batch_embeddings = [item.embedding for item in response.data]
                new_embeddings.extend(batch_embeddings)

            # Cache new embeddings and place them in results
            for text, embedding, idx in zip(texts_to_embed, new_embeddings, text_indices):
                self.cache.set_embedding(text, self.model_name, embedding)
                all_embeddings[idx] = embedding

        # Attach embeddings to chunks
        for chunk, embedding in zip(chunks, all_embeddings):
            chunk.embedding = embedding

        logger.info(f"Total embeddings processed: {len(chunks)}")
        return chunks

    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a query with caching.

        Args:
            query: Query text

        Returns:
            Query embedding vector
        """
        # Check cache first
        cached_embedding = self.cache.get_embedding(query, self.model_name)
        if cached_embedding:
            logger.info(f"Query embedding cache HIT for: '{query[:50]}...'")
            return cached_embedding

        # Cache miss - generate embedding
        client = self._get_client()

        logger.info(f"Query embedding cache MISS - generating using {self.model_name}")

        # Generate query embedding
        response = client.embeddings.create(input=[query], model=self.model_name)
        embedding = response.data[0].embedding

        # Cache the result
        self.cache.set_embedding(query, self.model_name, embedding)

        return embedding
