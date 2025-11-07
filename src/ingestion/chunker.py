"""Text chunking with overlap and token counting."""

import logging
from typing import List
from uuid import UUID

import tiktoken

from src.core.config import settings
from src.models.schemas import ChunkMetadata, Modality, TextChunk

logger = logging.getLogger(__name__)


class TextChunker:
    """Chunks text into smaller pieces with overlap."""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        encoding_name: str = "cl100k_base",
    ):
        """
        Initialize chunker.

        Args:
            chunk_size: Maximum tokens per chunk (defaults to config)
            chunk_overlap: Overlap tokens between chunks (defaults to config)
            encoding_name: tiktoken encoding name
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.encoding = tiktoken.get_encoding(encoding_name)

    def chunk(
        self,
        text: str,
        document_id: UUID,
        source: str,
        modality: Modality,
        section_title: str = None,
        page_number: int = None,
    ) -> List[TextChunk]:
        """
        Chunk text into overlapping segments.

        Args:
            text: Text to chunk
            document_id: ID of source document
            source: Source file path
            modality: Content modality
            section_title: Optional section title
            page_number: Optional page number

        Returns:
            List of TextChunk objects
        """
        if not text.strip():
            logger.warning(f"Empty text provided for chunking from {source}")
            return []

        # Encode text to tokens
        tokens = self.encoding.encode(text)
        total_tokens = len(tokens)

        chunks = []
        chunk_index = 0
        start_idx = 0

        while start_idx < total_tokens:
            # Get chunk tokens
            end_idx = min(start_idx + self.chunk_size, total_tokens)
            chunk_tokens = tokens[start_idx:end_idx]

            # Decode back to text
            chunk_text = self.encoding.decode(chunk_tokens).strip()

            if chunk_text:
                metadata = ChunkMetadata(
                    document_id=document_id,
                    source=source,
                    modality=modality,
                    chunk_index=chunk_index,
                    section_title=section_title,
                    page_number=page_number,
                )

                chunks.append(TextChunk(text=chunk_text, metadata=metadata))
                chunk_index += 1

            # Move to next chunk with overlap
            start_idx += self.chunk_size - self.chunk_overlap

            # Prevent infinite loop
            if start_idx >= total_tokens:
                break

        return chunks
