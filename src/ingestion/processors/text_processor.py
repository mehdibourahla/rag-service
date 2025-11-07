"""Text document processor using unstructured library."""

import logging
from pathlib import Path

from unstructured.partition.auto import partition

from src.ingestion.processors.base import BaseProcessor
from src.models.schemas import Modality

logger = logging.getLogger(__name__)


class TextProcessor(BaseProcessor):
    """Processes text documents (PDF, DOCX, TXT) using unstructured."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}

    def supports_file_type(self, file_path: Path) -> bool:
        """Check if file is a supported text document."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(self, file_path: Path) -> tuple[str, Modality]:
        """
        Extract text from document using unstructured.

        Args:
            file_path: Path to document

        Returns:
            Tuple of (extracted_text, modality)
        """
        try:
            logger.info(f"Processing text document: {file_path}")

            # Use unstructured to partition the document
            elements = partition(filename=str(file_path))

            # Extract text from all elements
            text_parts = [str(element) for element in elements if str(element).strip()]
            extracted_text = "\n\n".join(text_parts)

            if not extracted_text.strip():
                raise ValueError("No text content extracted from document")

            # Determine if OCR was needed (check for scanned PDF)
            modality = self._detect_modality(file_path, extracted_text)

            return extracted_text, modality

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            raise

    def _detect_modality(self, file_path: Path, text: str) -> Modality:
        """
        Determine if document was text-based or scanned.

        Simple heuristic: If PDF and very short text relative to file size,
        likely scanned. More sophisticated detection could use unstructured metadata.
        """
        if file_path.suffix.lower() == ".pdf":
            # Rough heuristic: scanned PDFs have low text-to-filesize ratio
            file_size_kb = file_path.stat().st_size / 1024
            text_length = len(text)

            if file_size_kb > 100 and text_length < 100:
                return Modality.SCANNED_TEXT

        return Modality.TEXT
