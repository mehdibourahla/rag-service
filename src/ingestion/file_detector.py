"""File type detection and routing logic."""

import mimetypes
from pathlib import Path

from src.models.schemas import FileType


class FileDetector:
    """Detects file type from path or content."""

    MIME_MAPPINGS = {
        "application/pdf": FileType.PDF,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
        "application/msword": FileType.DOC,
        "text/plain": FileType.TXT,
        "text/html": FileType.HTML,
        "text/markdown": FileType.MD,
    }

    EXT_MAPPINGS = {
        ".pdf": FileType.PDF,
        ".docx": FileType.DOCX,
        ".doc": FileType.DOC,
        ".txt": FileType.TXT,
        ".html": FileType.HTML,
        ".htm": FileType.HTML,
        ".md": FileType.MD,
        ".markdown": FileType.MD,
    }

    @classmethod
    def detect(cls, file_path: Path) -> FileType:
        """
        Detect file type from path.

        Args:
            file_path: Path to the file

        Returns:
            Detected FileType

        Raises:
            ValueError: If file type cannot be determined
        """
        # Try MIME type detection first
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type in cls.MIME_MAPPINGS:
            return cls.MIME_MAPPINGS[mime_type]

        # Fallback to extension
        ext = file_path.suffix.lower()
        if ext in cls.EXT_MAPPINGS:
            return cls.EXT_MAPPINGS[ext]

        raise ValueError(f"Unsupported file type: {file_path.name}")
