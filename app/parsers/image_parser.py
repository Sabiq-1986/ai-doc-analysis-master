"""
Image Parser - Multi-strategy OCR with AI Vision enhancement.
Supports 9 preprocessing strategies, Arabic + English OCR,
specialized ID document mode, table extraction, and handwriting.
Replaces the Docker OCR microservice with local Tesseract.
"""
import io
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from langchain_core.documents import Document

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Tesseract
try:
    import pytesseract
    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    TESSERACT_AVAILABLE = True
    try:
        _langs = pytesseract.get_languages()
        TESSERACT_LANGS = _langs
        HAS_ARABIC = 'ara' in _langs
        HAS_MRZ = 'mrz' in _langs
        logger.info(f"[OCR] Tesseract available. Languages: {_langs}")
    except Exception:
        TESSERACT_LANGS = ['eng']
        HAS_ARABIC = False
        HAS_MRZ = False
except ImportError:
    TESSERACT_AVAILABLE = False
    TESSERACT_LANGS = []
    HAS_ARABIC = False
    HAS_MRZ = False
    logger.warning("[OCR] pytesseract not installed")

# Try OpenCV
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


def _clean_ocr_text(text: str) -> str:
    """Clean OCR output to remove garbage lines."""
    if not text:
        return ""
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 2:
            continue
        # Count alphanumeric (including Arabic Unicode range)
        alphanumeric = sum(1 for c in line if c.isalnum())
        total = len(line)
        if total > 0 and alphanumeric < total * 0.3:
            continue
        words = line.split()
        single_char_words = sum(1 for w in words if len(w) == 1)
        if len(words) > 3 and single_char_words > len(words) * 0.5:
            continue
        noise_chars = line.count('-') + line.count('=') + line.count('|') + line.count('_')
        if noise_chars > len(line) * 0.3:
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines)


class ImageParser:
    """Multi-strategy OCR + AI Vision for images."""

    PREPROCESSING_STRATEGIES = [
        "original",
        "grayscale",
        "binary_threshold",
        "otsu_threshold",
        "adaptive_threshold",
        "denoise",
        "deskew",
        "contrast_enhance",
        "invert",
    ]

    def __init__(self, ai_enhancer=None):
        self.ai = ai_enhancer
        self.ocr_langs = self._build_lang_string()

    def _build_lang_string(self) -> str:
        """Build Tesseract language string based on available languages."""
        langs = []
        configured = settings.TESSERACT_LANGS.split('+')
        for lang in configured:
            lang = lang.strip()
            if lang in TESSERACT_LANGS:
                langs.append(lang)
        if not langs:
            langs = ['eng']
        return '+'.join(langs)

    def _preprocess_image(self, image: Image.Image, strategy: str) -> Image.Image:
        """Apply a preprocessing strategy to the image."""
        if strategy == "original":
            return image

        if strategy == "grayscale":
            return image.convert('L')

        if strategy == "binary_threshold":
            gray = image.convert('L')
            return gray.point(lambda x: 0 if x < 128 else 255, '1')

        if strategy == "otsu_threshold":
            if CV2_AVAILABLE:
                img_array = np.array(image.convert('L'))
                _, binary = cv2.threshold(img_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                return Image.fromarray(binary)
            return image.convert('L')

        if strategy == "adaptive_threshold":
            if CV2_AVAILABLE:
                img_array = np.array(image.convert('L'))
                binary = cv2.adaptiveThreshold(
                    img_array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 11, 2
                )
                return Image.fromarray(binary)
            return image.convert('L')

        if strategy == "denoise":
            if CV2_AVAILABLE:
                img_array = np.array(image.convert('L'))
                denoised = cv2.fastNlMeansDenoising(img_array, None, 10, 7, 21)
                return Image.fromarray(denoised)
            return image.filter(ImageFilter.MedianFilter(3))

        if strategy == "deskew":
            if CV2_AVAILABLE:
                img_array = np.array(image.convert('L'))
                coords = np.column_stack(np.where(img_array < 128))
                if len(coords) > 100:
                    angle = cv2.minAreaRect(coords)[-1]
                    if angle < -45:
                        angle = 90 + angle
                    if abs(angle) > 0.5:
                        (h, w) = img_array.shape
                        center = (w // 2, h // 2)
                        M = cv2.getRotationMatrix2D(center, angle, 1.0)
                        rotated = cv2.warpAffine(
                            img_array, M, (w, h),
                            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
                        )
                        return Image.fromarray(rotated)
            return image

        if strategy == "contrast_enhance":
            gray = image.convert('L')
            enhancer = ImageEnhance.Contrast(gray)
            return enhancer.enhance(2.0)

        if strategy == "invert":
            gray = image.convert('L')
            return ImageOps.invert(gray)

        return image

    def _ocr_with_strategy(self, image: Image.Image, strategy: str,
                           lang: str = None, psm: int = 3) -> str:
        """Run Tesseract OCR with a specific preprocessing strategy."""
        if not TESSERACT_AVAILABLE:
            return ""
        processed = self._preprocess_image(image, strategy)
        config = f'--psm {psm} --oem 3'
        ocr_lang = lang or self.ocr_langs
        try:
            text = pytesseract.image_to_string(processed, lang=ocr_lang, config=config)
            return text.strip()
        except Exception as e:
            logger.debug(f"[OCR] Strategy '{strategy}' failed: {e}")
            return ""

    def extract_text(self, image_data: bytes, filename: str = "image",
                     mode: str = "auto") -> dict:
        """
        Multi-strategy OCR extraction.

        Args:
            image_data: Raw image bytes
            filename: Original filename
            mode: "auto", "ocr", "id_document", "table", "handwriting"

        Returns:
            dict with keys: text, mode, confidence, metadata
        """
        try:
            image = Image.open(io.BytesIO(image_data))
        except Exception as e:
            logger.error(f"[OCR] Cannot open image: {e}")
            return {"text": "", "mode": "error", "confidence": 0, "metadata": {"error": str(e)}}

        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')

        result = {
            "text": "",
            "mode": "ocr",
            "confidence": 0.0,
            "metadata": {
                "filename": filename,
                "size": f"{image.size[0]}x{image.size[1]}",
                "format": image.format or "unknown"
            }
        }

        # ID document mode
        if mode == "id_document":
            return self.extract_text_id_document(image_data, filename)

        # Table mode - use AI vision
        if mode == "table":
            table_text = self.extract_table(image_data)
            if table_text:
                result["text"] = table_text
                result["mode"] = "ai_table"
                result["confidence"] = 0.8
                return result

        # Handwriting mode - use AI vision
        if mode == "handwriting":
            hw_text = self.extract_handwriting(image_data)
            if hw_text:
                result["text"] = hw_text
                result["mode"] = "ai_handwriting"
                result["confidence"] = 0.7
                return result

        # Auto/OCR mode: try multiple strategies
        best_text = ""
        best_len = 0
        best_strategy = "none"

        # Try key strategies with different PSM modes
        strategies_to_try = [
            ("contrast_enhance", 3),
            ("grayscale", 6),
            ("original", 3),
            ("otsu_threshold", 6),
            ("denoise", 3),
            ("adaptive_threshold", 6),
            ("deskew", 3),
        ]

        for strategy, psm in strategies_to_try:
            text = self._ocr_with_strategy(image, strategy, psm=psm)
            cleaned = _clean_ocr_text(text)
            if len(cleaned) > best_len:
                best_text = cleaned
                best_len = len(cleaned)
                best_strategy = strategy

        # Try with Arabic language if available and results are poor
        if HAS_ARABIC and best_len < 50:
            for strategy in ["contrast_enhance", "original", "otsu_threshold"]:
                text = self._ocr_with_strategy(image, strategy, lang='ara', psm=6)
                cleaned = _clean_ocr_text(text)
                if len(cleaned) > best_len:
                    best_text = cleaned
                    best_len = len(cleaned)
                    best_strategy = f"{strategy}+ara"

        # Try Arabic+English combined
        if HAS_ARABIC and best_len < 100:
            text = self._ocr_with_strategy(image, "contrast_enhance", lang='eng+ara', psm=3)
            cleaned = _clean_ocr_text(text)
            if len(cleaned) > best_len:
                best_text = cleaned
                best_len = len(cleaned)
                best_strategy = "contrast_enhance+eng+ara"

        # Try rotations if results are still poor
        if best_len < 50:
            for angle in [90, 180, 270]:
                rotated = image.rotate(angle, expand=True)
                text = self._ocr_with_strategy(rotated, "contrast_enhance", psm=6)
                cleaned = _clean_ocr_text(text)
                if len(cleaned) > best_len:
                    best_text = cleaned
                    best_len = len(cleaned)
                    best_strategy = f"rotation_{angle}"

        # AI Vision fallback for poor OCR results
        if best_len < 30 and self.ai and self.ai.is_vision_available():
            logger.info("[OCR] Poor OCR results, trying AI Vision...")
            ai_text = self.ai.understand_document(image_data)
            if ai_text and len(ai_text) > best_len:
                best_text = ai_text
                best_strategy = "ai_vision"

        # AI OCR enhancement if available and text exists
        if best_text and 20 < best_len < 500 and self.ai and self.ai.is_text_available():
            enhanced = self.ai.enhance_ocr(best_text)
            if enhanced and len(enhanced) >= len(best_text) * 0.8:
                best_text = enhanced
                best_strategy += "+ai_enhanced"

        result["text"] = best_text
        result["confidence"] = min(1.0, best_len / 200)
        result["metadata"]["strategy"] = best_strategy
        result["metadata"]["chars"] = best_len

        logger.info(f"[OCR] {filename}: {best_len} chars via {best_strategy}")
        return result

    def extract_text_id_document(self, image_data: bytes, filename: str = "image") -> dict:
        """Specialized ID document extraction with MRZ detection."""
        result = {
            "text": "",
            "mode": "id_document",
            "confidence": 0.0,
            "metadata": {"filename": filename}
        }

        # Try AI vision for ID documents first
        if self.ai and self.ai.is_vision_available():
            fields = self.ai.extract_id_fields(image_data)
            if fields and not fields.get('raw_extraction'):
                import json
                lines = ["[Identity Document]"]
                for key, value in fields.items():
                    if value and str(value).strip():
                        label = key.replace('_', ' ').title()
                        lines.append(f"{label}: {value}")
                result["text"] = '\n'.join(lines)
                result["confidence"] = 0.85
                result["metadata"]["method"] = "ai_vision"
                result["metadata"]["fields"] = fields
                return result

        # Fallback to standard OCR
        ocr_result = self.extract_text(image_data, filename, mode="ocr")
        ocr_result["mode"] = "id_document_ocr"
        return ocr_result

    def extract_table(self, image_data: bytes) -> Optional[str]:
        """Extract table from image using AI vision."""
        if self.ai and self.ai.is_vision_available():
            return self.ai.extract_table_from_image(image_data)
        return None

    def extract_handwriting(self, image_data: bytes) -> Optional[str]:
        """Extract handwritten text using AI vision."""
        if self.ai and self.ai.is_vision_available():
            return self.ai.read_handwriting(image_data)
        return None

    def ocr_image_bytes(self, image_data: bytes, lang: str = None) -> str:
        """Simple OCR extraction returning just text. Used by other parsers for embedded images."""
        result = self.extract_text(image_data, mode="ocr")
        return result.get("text", "")

    def parse(self, file_path: str) -> List[Document]:
        """
        Parse a standalone image file into LangChain Documents.

        Args:
            file_path: Path to image file

        Returns:
            List of LangChain Document objects
        """
        filename = Path(file_path).name

        with open(file_path, 'rb') as f:
            image_data = f.read()

        result = self.extract_text(image_data, filename=filename, mode="auto")
        text = result.get("text", "")

        if not text:
            logger.warning(f"[OCR] No text extracted from {filename}")
            return []

        metadata = {
            "source": filename,
            "type": "image",
            "extraction_mode": result.get("mode", "ocr"),
            "confidence": result.get("confidence", 0),
        }
        metadata.update(result.get("metadata", {}))

        return [Document(page_content=text, metadata=metadata)]
