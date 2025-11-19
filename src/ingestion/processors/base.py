"""Base processor interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from src.models.schemas import Modality


class BaseProcessor(ABC):
    """Base class for document processors."""

    @abstractmethod
    def process(self, file_path: Path) -> tuple[str, Modality]:
        """
        Process a file and extract text content.

        Args:
            file_path: Path to the file to process

        Returns:
            Tuple of (extracted_text, modality)
        """
        pass

    @abstractmethod
    def supports_file_type(self, file_path: Path) -> bool:
        """
        Check if this processor supports the given file type.

        Args:
            file_path: Path to check

        Returns:
            True if supported, False otherwise
        """
        pass
