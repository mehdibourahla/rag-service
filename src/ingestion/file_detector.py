"""File type detection and routing logic."""

import mimetypes
from pathlib import Path

from src.models.schemas import FileType


class FileDetector:
    """Detects file type from path or content."""

    # MIME type mappings to FileType
    MIME_MAPPINGS = {
        "application/pdf": FileType.PDF,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
        "application/msword": FileType.DOCX,
        "text/plain": FileType.TXT,
        "image/jpeg": FileType.IMAGE,
        "image/png": FileType.IMAGE,
        "image/gif": FileType.IMAGE,
        "image/bmp": FileType.IMAGE,
        "image/tiff": FileType.IMAGE,
        "audio/mpeg": FileType.AUDIO,
        "audio/wav": FileType.AUDIO,
        "audio/x-wav": FileType.AUDIO,
        "audio/ogg": FileType.AUDIO,
        "audio/flac": FileType.AUDIO,
        "audio/mp4": FileType.AUDIO,
        "video/mp4": FileType.VIDEO,
        "video/mpeg": FileType.VIDEO,
        "video/x-msvideo": FileType.VIDEO,
        "video/quicktime": FileType.VIDEO,
        "video/x-matroska": FileType.VIDEO,
    }

    # Extension fallback mappings
    EXT_MAPPINGS = {
        ".pdf": FileType.PDF,
        ".docx": FileType.DOCX,
        ".doc": FileType.DOCX,
        ".txt": FileType.TXT,
        ".jpg": FileType.IMAGE,
        ".jpeg": FileType.IMAGE,
        ".png": FileType.IMAGE,
        ".gif": FileType.IMAGE,
        ".bmp": FileType.IMAGE,
        ".tiff": FileType.IMAGE,
        ".tif": FileType.IMAGE,
        ".mp3": FileType.AUDIO,
        ".wav": FileType.AUDIO,
        ".ogg": FileType.AUDIO,
        ".flac": FileType.AUDIO,
        ".m4a": FileType.AUDIO,
        ".mp4": FileType.VIDEO,
        ".avi": FileType.VIDEO,
        ".mov": FileType.VIDEO,
        ".mkv": FileType.VIDEO,
        ".mpeg": FileType.VIDEO,
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
