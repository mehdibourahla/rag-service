"""Ingestion pipeline components."""

from src.ingestion.chunker import TextChunker
from src.ingestion.embedder import Embedder
from src.ingestion.file_detector import FileDetector
from src.ingestion.router import ProcessorRouter

__all__ = ["TextChunker", "Embedder", "FileDetector", "ProcessorRouter"]
