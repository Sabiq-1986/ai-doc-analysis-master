"""
AI Enhancer - Ollama Vision/Text AI for document understanding.
Provides AI-powered document analysis, table reconstruction,
handwriting recognition, OCR enhancement, and document classification.
All methods gracefully degrade when Ollama is not available.
"""
import base64
import io
import json
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AIEnhancer:
    """Ollama Vision/Text AI for intelligent document processing."""

    def __init__(self, ollama_url: str = None, vision_model: str = None, text_model: str = None):
        self.ollama_url = (ollama_url or settings.OLLAMA_BASE_URL).rstrip('/')
        self.vision_model = vision_model or settings.OLLAMA_VISION_MODEL
        self.text_model = text_model or settings.OLLAMA_MODEL
        self._vision_available = None
        self._text_available = None
        self.timeout = httpx.Timeout(300.0, connect=10.0)

    def _check_model(self, model_name: str) -> bool:
        """Check if a specific model is available in Ollama."""
        try:
            with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                resp = client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get('models', [])
                    available = any(
                        model_name in m.get('name', '') or m.get('name', '').startswith(model_name.split(':')[0])
                        for m in models
                    )
                    return available
        except Exception as e:
            logger.debug(f"[AI] Cannot reach Ollama: {e}")
        return False

    def is_vision_available(self) -> bool:
        """Check if the vision model is available."""
        if self._vision_available is None:
            self._vision_available = self._check_model(self.vision_model)
            status = "available" if self._vision_available else "not available"
            logger.info(f"[AI] Vision model ({self.vision_model}): {status}")
        return self._vision_available

    def is_text_available(self) -> bool:
        """Check if the text model is available."""
        if self._text_available is None:
            self._text_available = self._check_model(self.text_model)
            status = "available" if self._text_available else "not available"
            logger.info(f"[AI] Text model ({self.text_model}): {status}")
        return self._text_available

    def is_available(self) -> bool:
        """Check if any AI model is available."""
        return self.is_vision_available() or self.is_text_available()

    def _image_to_base64(self, image_data: bytes) -> str:
        """Convert image bytes to base64 string."""
        return base64.b64encode(image_data).decode('utf-8')

    def _call_ollama(self, model: str, prompt: str, images: list = None) -> Optional[str]:
        """Call Ollama API synchronously. Returns response text or None."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 4096}
        }
        if images:
            payload["images"] = images

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.ollama_url}/api/generate", json=payload)
                if resp.status_code == 200:
                    return resp.json().get('response', '').strip()
                else:
                    logger.warning(f"[AI] Ollama returned {resp.status_code}: {resp.text[:200]}")
        except httpx.TimeoutException:
            logger.warning(f"[AI] Ollama request timed out for model {model}")
        except Exception as e:
            logger.warning(f"[AI] Ollama request failed: {e}")
        return None

    def understand_document(self, image_data: bytes, prompt: str = None) -> Optional[str]:
        """
        Use vision model to understand a document image.
        Returns extracted/structured text or None if unavailable.
        """
        if not self.is_vision_available():
            return None

        if prompt is None:
            prompt = (
                "Analyze this document image carefully. Extract ALL text content you can see, "
                "preserving the structure and layout. Include headers, paragraphs, tables, "
                "labels, and any other visible text. If the document contains Arabic text, "
                "extract it accurately. Output the text content only, no commentary."
            )

        b64 = self._image_to_base64(image_data)
        return self._call_ollama(self.vision_model, prompt, images=[b64])

    def extract_table_from_image(self, image_data: bytes) -> Optional[str]:
        """
        Use vision model to reconstruct a table from an image into markdown.
        """
        if not self.is_vision_available():
            return None

        prompt = (
            "This image contains a table. Extract the table data and format it as a "
            "markdown table with proper headers and alignment. Preserve all cell values "
            "exactly as shown. If cells contain Arabic text, include it accurately. "
            "Output only the markdown table."
        )

        b64 = self._image_to_base64(image_data)
        return self._call_ollama(self.vision_model, prompt, images=[b64])

    def read_handwriting(self, image_data: bytes) -> Optional[str]:
        """
        Use vision model to transcribe handwritten text from an image.
        """
        if not self.is_vision_available():
            return None

        prompt = (
            "This image contains handwritten text. Carefully transcribe ALL the "
            "handwritten content you can see. Preserve line breaks and formatting. "
            "If the handwriting is in Arabic, transcribe it accurately. "
            "Output only the transcribed text."
        )

        b64 = self._image_to_base64(image_data)
        return self._call_ollama(self.vision_model, prompt, images=[b64])

    def enhance_ocr(self, raw_ocr_text: str) -> Optional[str]:
        """
        Use text model to fix OCR errors and clean up extracted text.
        """
        if not self.is_text_available():
            return None

        if not raw_ocr_text or len(raw_ocr_text.strip()) < 10:
            return raw_ocr_text

        prompt = (
            f"The following text was extracted using OCR and may contain errors. "
            f"Fix any obvious OCR mistakes (misread characters, broken words, "
            f"garbled text) while preserving the original meaning and structure. "
            f"If the text contains Arabic, fix Arabic OCR errors too. "
            f"Output only the corrected text, nothing else.\n\n"
            f"OCR TEXT:\n{raw_ocr_text}"
        )

        return self._call_ollama(self.text_model, prompt)

    def classify_document(self, image_data: bytes) -> Optional[dict]:
        """
        Detect document type from an image.
        Returns dict with type classification or None.
        """
        if not self.is_vision_available():
            return None

        prompt = (
            "Classify this document image. What type of document is it? "
            "Respond with ONLY a JSON object like: "
            '{"type": "passport", "confidence": "high", "language": "english"}\n'
            "Possible types: passport, id_card, invoice, receipt, letter, form, "
            "certificate, report, table, handwritten_note, other"
        )

        b64 = self._image_to_base64(image_data)
        result = self._call_ollama(self.vision_model, prompt, images=[b64])

        if result:
            try:
                # Try to parse JSON from response
                # Handle cases where model wraps in markdown code blocks
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                return json.loads(cleaned)
            except json.JSONDecodeError:
                return {"type": "unknown", "raw_response": result}
        return None

    def extract_id_fields(self, image_data: bytes) -> Optional[dict]:
        """
        Specialized extraction for passport, Emirates ID, and other ID documents.
        Uses vision model to extract structured fields.
        """
        if not self.is_vision_available():
            return None

        prompt = (
            "This is an identity document (passport, ID card, or similar). "
            "Extract ALL visible fields into a JSON object. Include fields like: "
            "full_name, surname, given_name, document_number, date_of_birth, "
            "expiry_date, nationality, sex, issuing_country, id_number, "
            "and any other visible fields. If text is in Arabic, include both "
            "Arabic and transliterated versions. Output ONLY valid JSON."
        )

        b64 = self._image_to_base64(image_data)
        result = self._call_ollama(self.vision_model, prompt, images=[b64])

        if result:
            try:
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                return json.loads(cleaned)
            except json.JSONDecodeError:
                return {"raw_extraction": result}
        return None

    def describe_image(self, image_data: bytes) -> Optional[str]:
        """
        Get a general description of an image for indexing.
        """
        if not self.is_vision_available():
            return None

        prompt = (
            "Describe what you see in this image in detail. Include any text, "
            "objects, people, or content visible. If there is text in Arabic or "
            "English, include it. Keep the description factual and concise."
        )

        b64 = self._image_to_base64(image_data)
        return self._call_ollama(self.vision_model, prompt, images=[b64])
