"""
Document Processor - Orchestrator that routes files to the appropriate parser.
Central factory that initializes all parsers with shared dependencies
(AIEnhancer, ImageParser, MRZReader).
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.documents import Document

from app.config import get_settings
from app.parsers.ai_enhancer import AIEnhancer
from app.parsers.image_parser import ImageParser
from app.parsers.mrz_reader import MRZReader
from app.parsers.text_parser import TextParser
from app.parsers.excel_parser import ExcelParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.word_parser import WordParser
from app.parsers.pptx_parser import PPTXParser

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentProcessor:
    """
    Orchestrator - routes files to the correct parser.
    Initializes all parsers with shared dependencies.
    """

    SUPPORTED_TYPES = {
        # Excel
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.xlsm': 'excel',
        # Tabular
        '.csv': 'text',
        '.tsv': 'text',
        # PDF
        '.pdf': 'pdf',
        # Word
        '.docx': 'word',
        '.doc': 'word',
        # PowerPoint
        '.pptx': 'pptx',
        '.ppt': 'pptx',
        # Text / Data
        '.txt': 'text',
        '.md': 'text',
        '.json': 'text',
        '.xml': 'text',
        '.html': 'text',
        '.htm': 'text',
        '.log': 'text',
        # Images
        '.png': 'image',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.gif': 'image',
        '.bmp': 'image',
        '.tiff': 'image',
        '.tif': 'image',
        '.webp': 'image',
    }

    # File types where parser output is already chunked (one doc per row/page/slide)
    ALREADY_CHUNKED = {
        '.xlsx', '.xls', '.xlsm',
        '.csv', '.tsv',
        '.pptx', '.ppt',
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp',
    }

    def __init__(self):
        """Initialize all parsers with shared dependencies."""
        logger.info("[PROC] Initializing document processor...")

        # Shared dependencies
        self.ai_enhancer = AIEnhancer(
            ollama_url=settings.OLLAMA_BASE_URL,
            vision_model=settings.OLLAMA_VISION_MODEL,
            text_model=settings.OLLAMA_MODEL,
        )

        self.image_parser = ImageParser(ai_enhancer=self.ai_enhancer)
        self.mrz_reader = MRZReader()

        # Initialize all parsers
        self.parsers: Dict[str, object] = {
            'pdf': PDFParser(
                image_parser=self.image_parser,
                ai_enhancer=self.ai_enhancer,
                mrz_reader=self.mrz_reader,
            ),
            'word': WordParser(image_parser=self.image_parser),
            'excel': ExcelParser(image_parser=self.image_parser),
            'pptx': PPTXParser(image_parser=self.image_parser),
            'image': self.image_parser,
            'text': TextParser(),
        }

        # Log capabilities
        ai_status = "available" if self.ai_enhancer.is_available() else "not available"
        mrz_status = "ONNX loaded" if self.mrz_reader.onnx_net else "Tesseract only"
        logger.info(f"[PROC] Parsers ready. AI Vision: {ai_status}. MRZ: {mrz_status}")

    def parse(self, file_path: str, file_type: str = None) -> List[Document]:
        """
        Route to the appropriate parser based on file type.

        Args:
            file_path: Path to the file
            file_type: File extension (e.g., '.pdf'). Auto-detected if not provided.

        Returns:
            List of LangChain Document objects with standardized metadata.
        """
        if file_type is None:
            file_type = Path(file_path).suffix.lower()
        else:
            file_type = file_type.lower()

        parser_key = self.SUPPORTED_TYPES.get(file_type)
        if not parser_key:
            raise ValueError(
                f"Unsupported file type: {file_type}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_TYPES.keys()))}"
            )

        parser = self.parsers[parser_key]
        filename = Path(file_path).name

        logger.info(f"[PROC] Processing '{filename}' with {parser_key} parser")

        try:
            if parser_key == 'image':
                # ImageParser.parse() handles standalone images
                documents = parser.parse(file_path)
            elif parser_key == 'text':
                # TextParser needs file_type for routing
                documents = parser.parse(file_path, file_type)
            else:
                documents = parser.parse(file_path)

            # Ensure all documents have required metadata
            for doc in documents:
                if 'source' not in doc.metadata:
                    doc.metadata['source'] = filename
                if 'type' not in doc.metadata:
                    doc.metadata['type'] = parser_key

            logger.info(f"[PROC] '{filename}': {len(documents)} chunks extracted")
            return documents

        except Exception as e:
            logger.error(f"[PROC] Error processing '{filename}': {e}")
            import traceback
            traceback.print_exc()
            raise

    def is_already_chunked(self, file_type: str) -> bool:
        """Check if a file type produces pre-chunked output."""
        return file_type.lower() in self.ALREADY_CHUNKED

    def get_supported_types(self) -> list:
        """Return list of supported file extensions."""
        return sorted(self.SUPPORTED_TYPES.keys())

    def get_parser_info(self) -> dict:
        """Return parser capabilities info."""
        return {
            "supported_types": self.get_supported_types(),
            "ai_vision": self.ai_enhancer.is_vision_available(),
            "ai_text": self.ai_enhancer.is_text_available(),
            "mrz_onnx": self.mrz_reader.onnx_net is not None,
            "parsers": list(self.parsers.keys()),
        }
