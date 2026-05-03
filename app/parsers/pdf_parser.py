"""
PDF Parser - PyMuPDF + pdfplumber + local Tesseract + AI Vision.
Layout-aware text extraction, precise table detection, OCR for scanned pages,
form fields, TOC/bookmarks, embedded images, and document properties.
"""
import io
import logging
import re
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# PyMuPDF
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

# pdfplumber for tables
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

# pypdf as fallback
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

# PIL for image handling
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class PDFParser:
    """
    Comprehensive PDF parser with multiple extraction strategies.
    Uses PyMuPDF for layout-aware text, pdfplumber for precise tables,
    local Tesseract for scanned pages, and AI Vision for complex layouts.
    """

    def __init__(self, image_parser=None, ai_enhancer=None, mrz_reader=None):
        self.image_parser = image_parser
        self.ai = ai_enhancer
        self.mrz = mrz_reader
        self.ocr_dpi = 300
        self.min_text_chars = 100  # threshold to trigger OCR

    def parse(self, file_path: str) -> List[Document]:
        """
        Parse PDF file using best available method.
        Returns list of LangChain Documents, one per page.
        """
        filename = Path(file_path).name
        documents = []

        # Extract document properties
        props = self._extract_properties(file_path)
        if props:
            documents.append(Document(
                page_content=props,
                metadata={"source": filename, "type": "pdf", "section": "properties"}
            ))

        # Extract table of contents
        toc = self._extract_toc(file_path)
        if toc:
            documents.append(Document(
                page_content=toc,
                metadata={"source": filename, "type": "pdf", "section": "toc"}
            ))

        # Extract form fields
        form_fields = self._extract_form_fields(file_path)
        if form_fields:
            documents.append(Document(
                page_content=form_fields,
                metadata={"source": filename, "type": "pdf", "section": "form_fields"}
            ))

        # Page-by-page extraction
        page_docs = self._extract_pages(file_path, filename)
        documents.extend(page_docs)

        # Extract embedded images
        image_docs = self._extract_embedded_images(file_path, filename)
        documents.extend(image_docs)

        if not documents:
            logger.warning(f"[PDF] No content extracted from {filename}")

        return documents

    def _extract_pages(self, file_path: str, filename: str) -> List[Document]:
        """Extract text from each page, with OCR fallback for scanned pages."""
        documents = []
        extraction_log = []

        if FITZ_AVAILABLE:
            try:
                doc = fitz.open(file_path)
                total_pages = len(doc)

                # Also open with pdfplumber for table extraction
                plumber_doc = None
                if PDFPLUMBER_AVAILABLE:
                    try:
                        plumber_doc = pdfplumber.open(file_path)
                    except Exception:
                        pass

                for page_num in range(total_pages):
                    page = doc[page_num]
                    page_text = ""
                    extraction_mode = "text"

                    # Primary: PyMuPDF text extraction (layout-aware)
                    text = page.get_text("text")
                    if text:
                        text = text.strip()

                    # Extract tables from pdfplumber
                    tables_text = ""
                    if plumber_doc and page_num < len(plumber_doc.pages):
                        tables_text = self._extract_tables_from_page(
                            plumber_doc.pages[page_num]
                        )

                    # Decide if OCR is needed
                    text_len = len(text) if text else 0

                    if text_len >= self.min_text_chars:
                        # Good text extraction
                        page_text = text
                        extraction_mode = "text"
                    else:
                        # Scanned page - need OCR
                        ocr_text = self._ocr_page(page, page_num, filename)
                        if ocr_text:
                            page_text = ocr_text
                            extraction_mode = "ocr"
                        elif text:
                            page_text = text
                            extraction_mode = "text_partial"

                    # Append tables if found
                    if tables_text:
                        page_text = f"{page_text}\n\n{tables_text}" if page_text else tables_text
                        if extraction_mode == "text":
                            extraction_mode = "text+tables"

                    if page_text and page_text.strip():
                        documents.append(Document(
                            page_content=page_text.strip(),
                            metadata={
                                "source": filename,
                                "type": "pdf",
                                "page": page_num + 1,
                                "total_pages": total_pages,
                                "extraction_mode": extraction_mode,
                            }
                        ))
                        extraction_log.append(f"Page {page_num+1}: {extraction_mode} ({len(page_text)} chars)")

                doc.close()
                if plumber_doc:
                    plumber_doc.close()

                if extraction_log:
                    logger.info(f"[PDF] {filename}: {len(extraction_log)} pages - "
                                f"{', '.join(set(e.split(':')[1].strip().split('(')[0].strip() for e in extraction_log))}")

                return documents

            except Exception as e:
                logger.error(f"[PDF] PyMuPDF failed for {filename}: {e}")

        # Fallback to pypdf
        if PYPDF_AVAILABLE:
            return self._extract_with_pypdf(file_path, filename)

        logger.error(f"[PDF] No PDF library available for {filename}")
        return []

    def _ocr_page(self, page, page_num: int, filename: str) -> Optional[str]:
        """OCR a scanned PDF page using local Tesseract."""
        if not self.image_parser:
            return None

        try:
            # Render page to image at configured DPI
            mat = fitz.Matrix(self.ocr_dpi / 72, self.ocr_dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")

            # Check for MRZ (passport/ID pages)
            if self.mrz:
                mrz_result = self.mrz.extract(img_data, filename=f"{filename}_p{page_num+1}")
                if mrz_result.get("has_mrz") and mrz_result.get("text"):
                    logger.info(f"[PDF] Page {page_num+1}: MRZ detected")
                    return mrz_result["text"]

            # Standard OCR
            result = self.image_parser.extract_text(
                img_data, filename=f"{filename}_p{page_num+1}", mode="auto"
            )
            return result.get("text", "")

        except Exception as e:
            logger.warning(f"[PDF] OCR failed for page {page_num+1}: {e}")
            return None

    def _extract_tables_from_page(self, plumber_page) -> str:
        """Extract tables from a pdfplumber page."""
        try:
            tables = plumber_page.extract_tables()
            if not tables:
                return ""

            table_texts = []
            for t_idx, table in enumerate(tables):
                if not table:
                    continue

                lines = []
                for row in table:
                    cells = [str(cell).strip() if cell else "" for cell in row]
                    if any(cells):
                        lines.append(" | ".join(cells))

                if lines:
                    table_texts.append(f"[Table {t_idx+1}]\n" + "\n".join(lines))

            return "\n\n".join(table_texts)

        except Exception as e:
            logger.debug(f"[PDF] Table extraction failed: {e}")
            return ""

    def _extract_with_pypdf(self, file_path: str, filename: str) -> List[Document]:
        """Fallback extraction using pypdf."""
        documents = []
        try:
            reader = PdfReader(file_path)
            total_pages = len(reader.pages)

            for page_num, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                text = text.strip()

                if len(text) < self.min_text_chars and self.image_parser and FITZ_AVAILABLE:
                    # Try OCR for this page
                    try:
                        doc = fitz.open(file_path)
                        fitz_page = doc[page_num]
                        ocr_text = self._ocr_page(fitz_page, page_num, filename)
                        doc.close()
                        if ocr_text and len(ocr_text) > len(text):
                            text = ocr_text
                    except Exception:
                        pass

                if text:
                    documents.append(Document(
                        page_content=text,
                        metadata={
                            "source": filename,
                            "type": "pdf",
                            "page": page_num + 1,
                            "total_pages": total_pages,
                            "extraction_mode": "pypdf",
                        }
                    ))

        except Exception as e:
            logger.error(f"[PDF] pypdf failed for {filename}: {e}")

        return documents

    def _extract_properties(self, file_path: str) -> Optional[str]:
        """Extract PDF document properties/metadata."""
        if not FITZ_AVAILABLE:
            return None

        try:
            doc = fitz.open(file_path)
            meta = doc.metadata
            doc.close()

            if not meta:
                return None

            props = ["[PDF Document Properties]"]
            field_map = {
                'title': 'Title',
                'author': 'Author',
                'subject': 'Subject',
                'keywords': 'Keywords',
                'creator': 'Creator',
                'producer': 'Producer',
                'creationDate': 'Created',
                'modDate': 'Modified',
            }

            for key, label in field_map.items():
                value = meta.get(key, '')
                if value and value.strip():
                    # Clean PDF date format
                    if 'Date' in label and value.startswith('D:'):
                        value = value[2:16]  # Extract YYYYMMDDHHMMSS
                        try:
                            from datetime import datetime
                            dt = datetime.strptime(value[:8], '%Y%m%d')
                            value = dt.strftime('%Y-%m-%d')
                        except Exception:
                            pass
                    props.append(f"{label}: {value}")

            if len(props) > 1:
                return '\n'.join(props)

        except Exception as e:
            logger.debug(f"[PDF] Property extraction failed: {e}")

        return None

    def _extract_toc(self, file_path: str) -> Optional[str]:
        """Extract table of contents / bookmarks."""
        if not FITZ_AVAILABLE:
            return None

        try:
            doc = fitz.open(file_path)
            toc = doc.get_toc()
            doc.close()

            if not toc:
                return None

            lines = ["[Table of Contents]"]
            for level, title, page in toc:
                indent = "  " * (level - 1)
                lines.append(f"{indent}{title} (page {page})")

            if len(lines) > 1:
                return '\n'.join(lines)

        except Exception as e:
            logger.debug(f"[PDF] TOC extraction failed: {e}")

        return None

    def _extract_form_fields(self, file_path: str) -> Optional[str]:
        """Extract PDF form fields."""
        if not PYPDF_AVAILABLE:
            return None

        try:
            reader = PdfReader(file_path)
            fields = reader.get_fields()

            if not fields:
                return None

            lines = ["[Form Fields]"]
            for name, field in fields.items():
                value = field.get('/V', '')
                field_type = field.get('/FT', '')

                if value:
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8')
                        except Exception:
                            value = str(value)
                    lines.append(f"{name}: {value}")

            if len(lines) > 1:
                return '\n'.join(lines)

        except Exception as e:
            logger.debug(f"[PDF] Form field extraction failed: {e}")

        return None

    def _extract_embedded_images(self, file_path: str, filename: str) -> List[Document]:
        """Extract and OCR embedded images from PDF."""
        if not FITZ_AVAILABLE or not self.image_parser:
            return []

        documents = []

        try:
            doc = fitz.open(file_path)

            for page_num in range(len(doc)):
                page = doc[page_num]
                images = page.get_images(full=True)

                for img_idx, img_info in enumerate(images):
                    xref = img_info[0]
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n > 4:  # CMYK
                            pix = fitz.Pixmap(fitz.csRGB, pix)

                        img_data = pix.tobytes("png")

                        if len(img_data) < 1000:  # Skip tiny images (icons, dots)
                            continue

                        result = self.image_parser.extract_text(
                            img_data,
                            filename=f"{filename}_p{page_num+1}_img{img_idx+1}",
                            mode="auto"
                        )

                        text = result.get("text", "")
                        if text and len(text.strip()) > 10:
                            documents.append(Document(
                                page_content=text,
                                metadata={
                                    "source": filename,
                                    "type": "pdf_image",
                                    "page": page_num + 1,
                                    "image_index": img_idx + 1,
                                }
                            ))

                    except Exception as e:
                        logger.debug(f"[PDF] Image extraction failed p{page_num+1} img{img_idx+1}: {e}")

            doc.close()

        except Exception as e:
            logger.debug(f"[PDF] Image extraction failed for {filename}: {e}")

        return documents
