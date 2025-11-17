"""Document processors for different file types."""

from src.ingestion.processors.base import BaseProcessor
from src.ingestion.processors.image_processor import ImageProcessor
from src.ingestion.processors.text_processor import TextProcessor

__all__ = [
    "BaseProcessor",
    "TextProcessor",
    "ImageProcessor",
]
