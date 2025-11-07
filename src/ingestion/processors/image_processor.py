"""Image processor using vision models for captioning and OCR."""

import logging
from pathlib import Path

import pytesseract
from PIL import Image
from transformers import AutoModel, AutoTokenizer

from src.ingestion.processors.base import BaseProcessor
from src.models.schemas import Modality

logger = logging.getLogger(__name__)


class ImageProcessor(BaseProcessor):
    """Processes images by generating captions using vision models and extracting text via OCR."""

    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif"}

    def __init__(
        self,
        model_name: str = "Salesforce/blip-image-captioning-large",
        enable_ocr: bool = True,
        ocr_languages: str = "eng+ara+fra+spa+deu+chi_sim",
    ):
        """
        Initialize image processor.

        Args:
            model_name: HuggingFace model for image captioning
            enable_ocr: Whether to run OCR on images (default: True)
            ocr_languages: Tesseract language codes (e.g., "eng+ara+fra")
        """
        self.model_name = model_name
        self.enable_ocr = enable_ocr
        self.ocr_languages = ocr_languages
        self._model = None
        self._processor = None

    def _load_model(self):
        """Lazy load the vision model."""
        if self._model is None:
            logger.info(f"Loading vision model: {self.model_name}")
            from transformers import BlipForConditionalGeneration, BlipProcessor

            self._processor = BlipProcessor.from_pretrained(self.model_name)
            self._model = BlipForConditionalGeneration.from_pretrained(self.model_name)
            logger.info("Vision model loaded successfully")

    def supports_file_type(self, file_path: Path) -> bool:
        """Check if file is a supported image."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def _extract_text_ocr(self, image: Image.Image) -> str:
        """
        Extract text from image using Tesseract OCR.

        Args:
            image: PIL Image object

        Returns:
            Extracted text string
        """
        try:
            # Use Tesseract with multiple languages
            text = pytesseract.image_to_string(image, lang=self.ocr_languages)
            return text.strip()
        except Exception as e:
            logger.warning(f"OCR extraction failed: {e}")
            return ""

    def process(self, file_path: Path) -> tuple[str, Modality]:
        """
        Generate caption and extract text from image.

        Args:
            file_path: Path to image

        Returns:
            Tuple of (combined_text, modality)
            - If OCR finds text: (caption + ocr_text, IMAGE_WITH_TEXT)
            - If no text found: (caption, IMAGE_CAPTION)
        """
        try:
            logger.info(f"Processing image: {file_path}")

            # Load model if not already loaded
            self._load_model()

            # Load and process image
            image = Image.open(file_path).convert("RGB")

            # Generate caption
            inputs = self._processor(image, return_tensors="pt")
            outputs = self._model.generate(**inputs, max_new_tokens=50)
            caption = self._processor.decode(outputs[0], skip_special_tokens=True)

            # Extract text via OCR if enabled
            ocr_text = ""
            if self.enable_ocr:
                ocr_text = self._extract_text_ocr(image)

            # Combine caption and OCR text
            if ocr_text:
                combined_text = (
                    f"Visual description: {caption}\n\n"
                    f"Text content (OCR):\n{ocr_text}"
                )
                modality = Modality.IMAGE_WITH_TEXT
            else:
                combined_text = caption
                modality = Modality.IMAGE_CAPTION

            return combined_text, modality

        except Exception as e:
            logger.error(f"Error processing image {file_path}: {e}")
            raise
