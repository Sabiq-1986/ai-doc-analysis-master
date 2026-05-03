"""
Text Parser - CSV, JSON, XML, log files, plain text, and markdown.
Includes column statistics for CSV, JSON normalization, XML tree extraction,
log file error detection, and multi-encoding support (including Arabic cp1256).
"""
import csv
import io
import json
import logging
import re
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Try pandas for statistics
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class TextParser:
    """Parser for CSV, TSV, JSON, XML, log, plain text, and markdown files."""

    ENCODINGS = ['utf-8-sig', 'utf-8', 'utf-16', 'latin-1', 'cp1252', 'cp1256', 'iso-8859-6']

    def parse(self, file_path: str, file_type: str = None) -> List[Document]:
        """Route to appropriate parser based on file type."""
        ext = file_type or Path(file_path).suffix.lower()
        filename = Path(file_path).name

        if ext in ('.csv', '.tsv'):
            return self._parse_csv(file_path, filename, ext)
        elif ext == '.json':
            return self._parse_json(file_path, filename)
        elif ext == '.xml':
            return self._parse_xml(file_path, filename)
        elif ext in ('.log',):
            return self._parse_log(file_path, filename)
        elif ext in ('.html', '.htm'):
            return self._parse_html(file_path, filename)
        else:
            return self._parse_text(file_path, filename)

    def _detect_encoding(self, file_path: str) -> str:
        """Try multiple encodings and return the first that works."""
        for enc in self.ENCODINGS:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    f.read(1024)
                return enc
            except (UnicodeDecodeError, UnicodeError):
                continue
        return 'utf-8'

    def _read_file(self, file_path: str) -> str:
        """Read file with auto-detected encoding."""
        encoding = self._detect_encoding(file_path)
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            return f.read()

    # =========================================================================
    #  CSV / TSV
    # =========================================================================

    def _parse_csv(self, file_path: str, filename: str, ext: str) -> List[Document]:
        """Parse CSV/TSV with column statistics."""
        encoding = self._detect_encoding(file_path)
        documents = []

        try:
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                sample = f.read(8192)

            # Auto-detect delimiter
            if ext == '.tsv':
                delimiter = '\t'
            else:
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                    delimiter = dialect.delimiter
                except csv.Error:
                    delimiter = ','

            # Read with pandas for statistics if available
            stats_text = ""
            if PANDAS_AVAILABLE:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, sep=delimiter,
                                     on_bad_lines='skip', nrows=10000)
                    stats_lines = [f"[CSV Summary: {len(df)} rows x {len(df.columns)} columns]"]
                    stats_lines.append(f"Columns: {', '.join(df.columns.tolist())}")

                    for col in df.columns:
                        if pd.api.types.is_numeric_dtype(df[col]):
                            stats_lines.append(
                                f"  {col}: min={df[col].min()}, max={df[col].max()}, "
                                f"avg={df[col].mean():.2f}, count={df[col].count()}"
                            )

                    stats_text = '\n'.join(stats_lines)
                    documents.append(Document(
                        page_content=stats_text,
                        metadata={"source": filename, "type": "csv", "section": "statistics"}
                    ))
                except Exception as e:
                    logger.debug(f"[CSV] Pandas stats failed: {e}")

            # Row-by-row extraction
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                reader = csv.reader(f, delimiter=delimiter)
                headers = None

                for row_idx, row in enumerate(reader):
                    if row_idx == 0:
                        headers = row
                        continue

                    if not any(cell.strip() for cell in row):
                        continue

                    if headers:
                        row_text = ' | '.join(
                            f"{h}: {v}" for h, v in zip(headers, row) if v.strip()
                        )
                    else:
                        row_text = ' | '.join(cell for cell in row if cell.strip())

                    if row_text.strip():
                        documents.append(Document(
                            page_content=row_text,
                            metadata={
                                "source": filename,
                                "type": "csv",
                                "row": row_idx + 1,
                            }
                        ))

        except Exception as e:
            logger.error(f"[CSV] Error parsing {filename}: {e}")
            # Fallback to plain text
            return self._parse_text(file_path, filename)

        if not documents:
            return self._parse_text(file_path, filename)

        return documents

    # =========================================================================
    #  JSON
    # =========================================================================

    def _parse_json(self, file_path: str, filename: str) -> List[Document]:
        """Parse JSON with normalization to tables."""
        content = self._read_file(file_path)
        documents = []

        try:
            data = json.loads(content)

            # Pretty-print for indexing
            pretty = json.dumps(data, indent=2, ensure_ascii=False)

            # Try pandas normalization for tabular JSON
            if PANDAS_AVAILABLE and isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                try:
                    df = pd.json_normalize(data)
                    summary = f"[JSON Table: {len(df)} records x {len(df.columns)} columns]\n"
                    summary += f"Columns: {', '.join(df.columns.tolist())}\n"

                    for col in df.columns:
                        if pd.api.types.is_numeric_dtype(df[col]):
                            summary += (
                                f"  {col}: min={df[col].min()}, max={df[col].max()}, "
                                f"avg={df[col].mean():.2f}\n"
                            )

                    documents.append(Document(
                        page_content=summary,
                        metadata={"source": filename, "type": "json", "section": "summary"}
                    ))

                    # Individual records
                    for idx, record in enumerate(data[:1000]):  # cap at 1000
                        record_text = json.dumps(record, indent=2, ensure_ascii=False)
                        documents.append(Document(
                            page_content=record_text,
                            metadata={"source": filename, "type": "json", "record": idx + 1}
                        ))
                    return documents
                except Exception:
                    pass

            # For non-tabular JSON, return as pretty-printed text
            documents.append(Document(
                page_content=pretty,
                metadata={"source": filename, "type": "json"}
            ))

        except json.JSONDecodeError:
            # Not valid JSON, treat as text
            documents.append(Document(
                page_content=content,
                metadata={"source": filename, "type": "json", "parse_error": "invalid_json"}
            ))

        return documents

    # =========================================================================
    #  XML
    # =========================================================================

    def _parse_xml(self, file_path: str, filename: str) -> List[Document]:
        """Parse XML with tree structure extraction."""
        content = self._read_file(file_path)
        documents = []

        try:
            root = ElementTree.fromstring(content)

            # Build tree structure
            tree_lines = [f"[XML Document: {root.tag}]"]
            self._xml_tree_walk(root, tree_lines, depth=0, max_depth=10)
            tree_text = '\n'.join(tree_lines)

            documents.append(Document(
                page_content=tree_text,
                metadata={"source": filename, "type": "xml", "root_tag": root.tag}
            ))

        except ElementTree.ParseError:
            # Not valid XML, return as text
            documents.append(Document(
                page_content=content,
                metadata={"source": filename, "type": "xml", "parse_error": "invalid_xml"}
            ))

        return documents

    def _xml_tree_walk(self, element, lines: list, depth: int, max_depth: int):
        """Recursively walk XML tree and extract text content."""
        if depth > max_depth:
            return

        indent = "  " * depth
        tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag

        # Element attributes
        attrs = ' '.join(f'{k}="{v}"' for k, v in element.attrib.items())
        header = f"{indent}<{tag}" + (f" {attrs}" if attrs else "") + ">"

        # Text content
        text = (element.text or '').strip()
        if text:
            if len(text) > 200:
                lines.append(f"{header} {text[:200]}...")
            else:
                lines.append(f"{header} {text}")
        elif list(element):
            lines.append(header)

        for child in element:
            self._xml_tree_walk(child, lines, depth + 1, max_depth)

    # =========================================================================
    #  LOG FILES
    # =========================================================================

    def _parse_log(self, file_path: str, filename: str) -> List[Document]:
        """Parse log files with error/warning detection."""
        content = self._read_file(file_path)
        documents = []

        lines = content.split('\n')

        # Detect errors and warnings
        error_lines = []
        warning_lines = []

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in ['error', 'exception', 'fatal', 'critical', 'fail']):
                error_lines.append(f"L{i+1}: {line.strip()}")
            elif any(kw in line_lower for kw in ['warn', 'warning', 'caution']):
                warning_lines.append(f"L{i+1}: {line.strip()}")

        # Summary
        summary_parts = [f"[Log File: {filename}, {len(lines)} lines]"]
        if error_lines:
            summary_parts.append(f"\nErrors ({len(error_lines)}):")
            summary_parts.extend(error_lines[:50])
        if warning_lines:
            summary_parts.append(f"\nWarnings ({len(warning_lines)}):")
            summary_parts.extend(warning_lines[:50])

        if error_lines or warning_lines:
            documents.append(Document(
                page_content='\n'.join(summary_parts),
                metadata={
                    "source": filename, "type": "log", "section": "issues",
                    "error_count": len(error_lines), "warning_count": len(warning_lines)
                }
            ))

        # Full content
        documents.append(Document(
            page_content=content,
            metadata={"source": filename, "type": "log"}
        ))

        return documents

    # =========================================================================
    #  HTML
    # =========================================================================

    def _parse_html(self, file_path: str, filename: str) -> List[Document]:
        """Parse HTML by stripping tags and extracting text."""
        content = self._read_file(file_path)

        # Strip HTML tags
        text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', content, flags=re.IGNORECASE)
        text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Decode HTML entities
        import html
        text = html.unescape(text)

        if not text:
            return []

        return [Document(
            page_content=text,
            metadata={"source": filename, "type": "html"}
        )]

    # =========================================================================
    #  PLAIN TEXT / MARKDOWN
    # =========================================================================

    def _parse_text(self, file_path: str, filename: str) -> List[Document]:
        """Parse plain text and markdown files."""
        content = self._read_file(file_path)

        if not content.strip():
            return []

        return [Document(
            page_content=content,
            metadata={"source": filename, "type": "text"}
        )]
