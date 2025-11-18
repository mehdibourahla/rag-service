"""Document processing router that directs files to appropriate processors."""

import logging
from pathlib import Path
from typing import List

from src.ingestion.file_detector import FileDetector
from src.ingestion.processors import (
    BaseProcessor,
    # ImageProcessor,  # REMOVED: Phase 1 is text-only, add back for multi-modal support
    TextProcessor,
)
from src.models.schemas import FileType, Modality

logger = logging.getLogger(__name__)


class ProcessorRouter:
    """Routes files to appropriate processors based on file type."""

    def __init__(self):
        """Initialize router with all processors."""
        self.processors: List[BaseProcessor] = [
            TextProcessor(),
            # ImageProcessor(),  # REMOVED: Phase 1 is text-only
        ]

    def route(self, file_path: Path) -> tuple[str, Modality]:
        """
        Route file to appropriate processor and extract content.

        Args:
            file_path: Path to file to process

        Returns:
            Tuple of (extracted_text, modality)

        Raises:
            ValueError: If no suitable processor found
        """
        # Find matching processor
        for processor in self.processors:
            if processor.supports_file_type(file_path):
                return processor.process(file_path)

        raise ValueError(f"No processor found for file: {file_path.name}")
