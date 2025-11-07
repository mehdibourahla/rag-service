"""Audio/Video processor using Whisper for transcription."""

import logging
from pathlib import Path

import whisper

from src.ingestion.processors.base import BaseProcessor
from src.models.schemas import Modality

logger = logging.getLogger(__name__)


class AudioProcessor(BaseProcessor):
    """Processes audio files using Whisper ASR."""

    SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}

    def __init__(self, model_size: str = "base"):
        """
        Initialize audio processor.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self._model = None

    def _load_model(self):
        """Lazy load the Whisper model."""
        if self._model is None:
            logger.info(f"Loading Whisper model: {self.model_size}")
            self._model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded successfully")

    def supports_file_type(self, file_path: Path) -> bool:
        """Check if file is a supported audio format."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(self, file_path: Path) -> tuple[str, Modality]:
        """
        Transcribe audio file.

        Args:
            file_path: Path to audio file

        Returns:
            Tuple of (transcript_text, AUDIO_TRANSCRIPT modality)
        """
        try:
            logger.info(f"Transcribing audio: {file_path}")

            # Load model if not already loaded
            self._load_model()

            # Transcribe
            result = self._model.transcribe(str(file_path))
            transcript = result["text"].strip()

            if not transcript:
                raise ValueError("No transcript generated from audio")

            return transcript, Modality.AUDIO_TRANSCRIPT

        except Exception as e:
            logger.error(f"Error transcribing audio {file_path}: {e}")
            raise


class VideoProcessor(BaseProcessor):
    """Processes video files by extracting audio and transcribing."""

    SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".mpeg"}

    def __init__(self, model_size: str = "base"):
        """
        Initialize video processor.

        Args:
            model_size: Whisper model size for audio transcription
        """
        self.model_size = model_size
        self._model = None

    def _load_model(self):
        """Lazy load the Whisper model."""
        if self._model is None:
            logger.info(f"Loading Whisper model: {self.model_size}")
            self._model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded successfully")

    def supports_file_type(self, file_path: Path) -> bool:
        """Check if file is a supported video format."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(self, file_path: Path) -> tuple[str, Modality]:
        """
        Transcribe video file (extract audio and transcribe).

        Args:
            file_path: Path to video file

        Returns:
            Tuple of (transcript_text, VIDEO_TRANSCRIPT modality)
        """
        try:
            logger.info(f"Transcribing video: {file_path}")

            # Load model if not already loaded
            self._load_model()

            # Whisper can handle video files directly (extracts audio internally)
            result = self._model.transcribe(str(file_path))
            transcript = result["text"].strip()

            if not transcript:
                raise ValueError("No transcript generated from video")

            return transcript, Modality.VIDEO_TRANSCRIPT

        except Exception as e:
            logger.error(f"Error transcribing video {file_path}: {e}")
            raise
