"""
Modular document parsers package.
Each parser returns List[langchain_core.documents.Document] with standardized metadata.
"""
from app.parsers.ai_enhancer import AIEnhancer
from app.parsers.image_parser import ImageParser
from app.parsers.mrz_reader import MRZReader
from app.parsers.text_parser import TextParser
from app.parsers.excel_parser import ExcelParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.word_parser import WordParser
from app.parsers.pptx_parser import PPTXParser
from app.parsers.document_processor import DocumentProcessor

__all__ = [
    'AIEnhancer', 'ImageParser', 'MRZReader', 'TextParser',
    'ExcelParser', 'PDFParser', 'WordParser', 'PPTXParser',
    'DocumentProcessor',
]
