"""Qdrant vector store integration."""

import logging
from typing import List, Optional
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.core.config import settings
from src.models.schemas import ChunkMetadata, TextChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """Qdrant vector store for dense retrieval."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = None,
    ):
        """
        Initialize vector store.

        Args:
            host: Qdrant host (defaults to config)
            port: Qdrant port (defaults to config)
            collection_name: Collection name (defaults to config)
        """
        self.host = host or settings.qdrant_host
        self.port = port or settings.qdrant_port
        self.collection_name = collection_name or settings.qdrant_collection
        self.client = QdrantClient(host=self.host, port=self.port)
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            logger.info(f"Creating Qdrant collection: {self.collection_name}")
            # text-embedding-3-small produces 1536-dimensional vectors by default
            # text-embedding-3-large produces 3072-dimensional vectors by default
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
            logger.info(f"Collection {self.collection_name} created")
        else:
            logger.info(f"Collection {self.collection_name} already exists")

    def add_chunks(self, chunks: List[TextChunk]) -> int:
        """
        Add chunks to vector store.

        Args:
            chunks: List of TextChunk objects with embeddings

        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0

        points = []
        for chunk in chunks:
            if not chunk.embedding:
                logger.warning(f"Chunk {chunk.metadata.chunk_id} has no embedding, skipping")
                continue

            point = PointStruct(
                id=str(chunk.metadata.chunk_id),
                vector=chunk.embedding,
                payload={
                    "text": chunk.text,
                    "document_id": str(chunk.metadata.document_id),
                    "source": chunk.metadata.source,
                    "modality": chunk.metadata.modality.value,
                    "chunk_index": chunk.metadata.chunk_index,
                    "section_title": chunk.metadata.section_title,
                    "page_number": chunk.metadata.page_number,
                    "created_at": chunk.metadata.created_at.isoformat(),
                },
            )
            points.append(point)

        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"Added {len(points)} chunks to vector store")

        return len(points)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filter_dict: Optional[dict] = None,
    ) -> List[dict]:
        """
        Search for similar chunks.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filter_dict: Optional filters (e.g., {"document_id": "..."})

        Returns:
            List of search results with text, metadata, and scores
        """
        logger.info(f"Searching vector store (top_k={top_k})")

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=filter_dict,
        )

        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "text": result.payload["text"],
                    "score": result.score,
                    "metadata": {
                        "chunk_id": result.id,
                        "document_id": result.payload["document_id"],
                        "source": result.payload["source"],
                        "modality": result.payload["modality"],
                        "chunk_index": result.payload["chunk_index"],
                        "section_title": result.payload.get("section_title"),
                        "page_number": result.payload.get("page_number"),
                    },
                }
            )

        logger.info(f"Found {len(formatted_results)} results")
        return formatted_results

    def delete_by_document(self, document_id: UUID) -> int:
        """
        Delete all chunks for a document.

        Args:
            document_id: Document ID

        Returns:
            Number of chunks deleted
        """
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        logger.info(f"Deleting chunks for document {document_id}")

        # Delete points matching document_id
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(document_id)),
                    )
                ]
            ),
        )

        logger.info(f"Deleted chunks for document {document_id}")
        return 1  # Qdrant doesn't return count

    def count(self) -> int:
        """Get total number of chunks in store."""
        collection_info = self.client.get_collection(self.collection_name)
        return collection_info.points_count
