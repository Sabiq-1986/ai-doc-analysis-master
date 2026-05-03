# app/services/excel_query_service.py
"""
Excel Query Service - Uses pandas to answer questions about Excel files.
Instead of relying on LLM to calculate from text chunks, this service
executes actual pandas operations on the data.
"""
import os
import re
import json
import httpx
from typing import Optional, Dict, Any, List
from pathlib import Path

import pandas as pd
import openpyxl

from app.config import get_settings

settings = get_settings()


class ExcelQueryService:
    """Query Excel files using pandas for accurate calculations."""

    def __init__(self):
        self.ollama_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL

    def load_excel(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """Load all sheets from an Excel file into DataFrames.

        Handles various Excel structures:
        - Simple tables with headers in row 1
        - Tables with title rows before headers
        - Multi-row merged headers (e.g. Month over Week columns)
        """
        try:
            xlsx = pd.ExcelFile(file_path)
            sheets = {}
            for sheet_name in xlsx.sheet_names:
                # Read raw data (no header) to analyze structure
                raw = pd.read_excel(xlsx, sheet_name=sheet_name, header=None, nrows=10)
                max_try = min(5, len(raw))

                # Detect title rows: rows with a single unique non-null value
                # (indicates a merged title cell like "Leaves 2025" spanning all columns)
                title_rows = set()
                if raw.shape[1] > 1:
                    for r in range(min(3, max_try)):
                        row_vals = raw.iloc[r].dropna()
                        unique_vals = row_vals.unique()
                        if len(unique_vals) <= 1:
                            title_rows.add(r)
                            print(f"[EXCEL_QUERY] Row {r} detected as title row in '{sheet_name}'")

                best_df = None
                best_score = -1

                # Try single-row headers (0-4)
                for header_row in range(max_try):
                    try:
                        test_df = pd.read_excel(xlsx, sheet_name=sheet_name, header=header_row)
                        if len(test_df) == 0:
                            continue
                        score = self._score_single_header(test_df, header_row, title_rows)
                        if score > best_score:
                            best_score = score
                            best_df = test_df
                    except:
                        continue

                # Try multi-row (adjacent pair) headers — handles merged headers
                # Skip pairs that start with a title row
                for r in range(max(max_try - 1, 1)):
                    if r in title_rows:
                        continue
                    try:
                        multi_df = pd.read_excel(xlsx, sheet_name=sheet_name, header=[r, r + 1])
                        if len(multi_df) == 0:
                            continue
                        flat_cols = self._flatten_multi_columns(multi_df.columns)
                        multi_df.columns = flat_cols

                        generic = sum(1 for c in flat_cols if c.startswith('Col_'))
                        unique = len(set(flat_cols))
                        duplicates = len(flat_cols) - unique
                        numeric_hdrs = sum(1 for c in flat_cols
                                          if not c.startswith('Col_') and
                                          c.replace('_', '').replace('.', '').replace('-', '').isdigit())
                        first_col_valid = multi_df.iloc[:, 0].notna().sum()

                        # Penalize duplicates heavily (sign of wrong header rows)
                        # Penalize numeric headers (data row used as header)
                        score = (unique - generic) * 10 + first_col_valid - duplicates * 15 - numeric_hdrs * 8

                        if score > best_score:
                            best_score = score
                            best_df = multi_df
                            print(f"[EXCEL_QUERY] Using multi-row headers [{r},{r+1}] for sheet '{sheet_name}'")
                    except Exception as e:
                        print(f"[EXCEL_QUERY] Multi-row [{r},{r+1}] failed: {e}")
                        continue

                if best_df is None:
                    best_df = pd.read_excel(xlsx, sheet_name=sheet_name)

                # Clean column names - replace Unnamed with Col_N
                new_cols = []
                for i, c in enumerate(best_df.columns):
                    c_str = str(c).strip()
                    if 'Unnamed:' in c_str:
                        new_cols.append(f'Col_{i+1}')
                    else:
                        new_cols.append(c_str)
                best_df.columns = new_cols

                # Drop completely empty rows
                best_df = best_df.dropna(how='all')

                sheets[sheet_name] = best_df
                print(f"[EXCEL_QUERY] Sheet '{sheet_name}': {len(best_df)} rows, columns: {list(best_df.columns[:10])}...")
            return sheets
        except Exception as e:
            print(f"[EXCEL_QUERY] Error loading {file_path}: {e}")
            return {}

    def _score_single_header(self, df: pd.DataFrame, header_row: int, title_rows: set) -> float:
        """Score a single-row header choice."""
        unnamed = sum(1 for c in df.columns if 'Unnamed:' in str(c))
        named = len(df.columns) - unnamed
        first_col_valid = df.iloc[:, 0].notna().sum()

        # Penalize title rows used as headers
        title_penalty = 50 if header_row in title_rows else 0

        # Penalize numeric-looking column headers (likely a data row, not a header)
        numeric_hdrs = sum(1 for c in df.columns
                          if 'Unnamed:' not in str(c) and
                          str(c).replace('.', '').replace('-', '').isdigit())

        return named * 10 + first_col_valid - title_penalty - numeric_hdrs * 8

    def _flatten_multi_columns(self, columns) -> List[str]:
        """Flatten MultiIndex columns into single-level names."""
        flat_cols = []
        for col in columns:
            parts = [str(p).strip() for p in col
                     if 'Unnamed' not in str(p) and str(p).strip()]
            flat_cols.append('_'.join(parts) if parts else f'Col_{len(flat_cols)+1}')
        return flat_cols

    def get_excel_summary(self, file_path: str) -> str:
        """Get a summary of Excel file structure for the LLM."""
        sheets = self.load_excel(file_path)
        if not sheets:
            return "Could not load Excel file."

        summary_parts = [f"Excel File: {Path(file_path).name}\n"]

        for sheet_name, df in sheets.items():
            summary_parts.append(f"\n=== Sheet: {sheet_name} ===")
            summary_parts.append(f"Rows: {len(df)}, Columns: {len(df.columns)}")

            all_cols = df.columns.tolist()
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            text_cols = [c for c in all_cols if c not in numeric_cols]

            # For wide spreadsheets (>15 cols), show compact summary
            if len(all_cols) > 15:
                summary_parts.append(f"Text columns: {text_cols}")
                # Detect column patterns (e.g., Jan_W1..Dec_W5)
                patterns = self._detect_column_patterns(numeric_cols)
                if patterns:
                    summary_parts.append(f"Numeric column patterns: {patterns}")
                else:
                    summary_parts.append(f"Numeric columns ({len(numeric_cols)}): {numeric_cols[:10]}...")

                # Show sample with only key columns (text cols + first few numeric)
                sample_cols = text_cols[:3] + numeric_cols[:5]
                if len(df) > 0:
                    summary_parts.append(f"\nSample data (first 5 rows, key columns):")
                    sample = df[sample_cols].head(5).to_string(index=False)
                    summary_parts.append(sample)

                # Show per-row totals for a few rows to help LLM understand data
                if numeric_cols:
                    summary_parts.append(f"\nRow totals (sum of all {len(numeric_cols)} numeric columns):")
                    row_totals = df[numeric_cols].sum(axis=1)
                    for i in range(min(5, len(df))):
                        name = df.iloc[i][text_cols[1]] if len(text_cols) > 1 else df.iloc[i][text_cols[0]] if text_cols else f"Row {i}"
                        summary_parts.append(f"  {name}: {int(row_totals.iloc[i])}")
            else:
                summary_parts.append(f"Columns: {', '.join(all_cols)}")
                # Show first few rows as sample
                if len(df) > 0:
                    summary_parts.append("\nSample data (first 5 rows):")
                    sample = df.head(5).to_string(index=False)
                    summary_parts.append(sample)

                if numeric_cols:
                    summary_parts.append(f"\nNumeric columns: {numeric_cols}")

            # Show value counts for categorical columns
            for col in text_cols[:3]:
                if df[col].dtype == 'object':
                    unique = df[col].nunique()
                    if 2 <= unique <= 10:
                        counts = df[col].value_counts().head(5).to_dict()
                        summary_parts.append(f"\n'{col}' values: {counts}")

        return '\n'.join(summary_parts)

    def _detect_column_patterns(self, columns: List[str]) -> str:
        """Detect repeating patterns in column names (e.g., Jan_W1..Dec_W5)."""
        if not columns:
            return ""
        # Check for prefix_suffix pattern
        parts_list = [c.rsplit('_', 1) for c in columns if '_' in c]
        if len(parts_list) < len(columns) * 0.5:
            return ""
        prefixes = sorted(set(p[0] for p in parts_list))
        suffixes = sorted(set(p[1] for p in parts_list if len(p) > 1))
        if prefixes and suffixes:
            return f"{prefixes[0]}__{prefixes[-1]} x {suffixes[0]}__{suffixes[-1]} ({len(columns)} columns: {columns[0]}...{columns[-1]})"
        return ""

    async def generate_pandas_code(self, question: str, excel_summary: str) -> str:
        """Use LLM to generate pandas code for the question."""
        # Get first sheet name from summary
        first_sheet = "Sheet1"
        if "=== Sheet:" in excel_summary:
            match = re.search(r"=== Sheet: (.+?) ===", excel_summary)
            if match:
                first_sheet = match.group(1)

        prompt = f"""Generate Python pandas code to answer this question about an Excel file.

{excel_summary}

QUESTION: {question}

RULES:
1. Output ONLY valid Python code, no explanations or text
2. The DataFrame is already loaded as: df = sheets['{first_sheet}']
3. Store the final answer in a variable called 'result'
4. For text matching use .str.contains(pattern, case=False, na=False)

PATTERNS:
- Filter by name: row = df[df['Name'].str.contains('Smith', case=False, na=False)]
- Sum all numeric cols for a row: result = row.select_dtypes(include='number').sum(axis=1).iloc[0]
- Sum one column: result = df['Amount'].sum()
- Count rows: result = len(df[df['Type'] == 'Call'])
- Group and count: result = df['Type'].value_counts().to_dict()
- Max value row: result = df.loc[df['Amount'].idxmax(), 'Name']

df = sheets['{first_sheet}']
"""

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 500}
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    code = result.get("response", "")
                    print(f"[EXCEL_QUERY] LLM raw response: {code[:300]}")
                    code = self._extract_code(code)
                    return code
                else:
                    print(f"[EXCEL_QUERY] Ollama returned status {response.status_code}: {response.text[:200]}")
        except Exception as e:
            print(f"[EXCEL_QUERY] Error generating code: {type(e).__name__}: {e}")

        return ""

    def _extract_code(self, text: str) -> str:
        """Extract Python code from markdown code blocks."""
        # Try to find code between ```python and ```
        match = re.search(r'```python\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find code between ``` and ```
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Clean up any trailing ``` (partial code block)
        code = text.strip()
        code = re.sub(r'```\s*$', '', code)  # Remove trailing ```
        code = re.sub(r'^```\w*\s*', '', code)  # Remove leading ```python or ```

        # Remove any lines that are just ```
        lines = [line for line in code.split('\n') if line.strip() != '```']
        return '\n'.join(lines).strip()

    def execute_pandas_query(self, sheets: Dict[str, pd.DataFrame], code: str) -> Any:
        """Safely execute pandas code and return result."""
        if not code:
            return None

        # Clean up the code
        code = code.strip()
        # Remove any stray markdown artifacts
        code = code.replace('```python', '').replace('```', '')
        # Handle common issues
        code = code.strip()

        # Create a safe execution environment
        # Add the first sheet as 'df' for convenience
        first_sheet = list(sheets.values())[0] if sheets else pd.DataFrame()
        safe_globals = {
            'pd': pd,
            'sheets': sheets,
            'df': first_sheet,  # Convenience shortcut
            'len': len,
            'sum': sum,
            'min': min,
            'max': max,
        }
        safe_locals = {}

        try:
            # Execute the generated code
            exec(code, safe_globals, safe_locals)

            # Get the result
            result = safe_locals.get('result')
            return result
        except Exception as e:
            print(f"[EXCEL_QUERY] Error executing code: {e}")
            print(f"[EXCEL_QUERY] Code was:\n{code}")
            return f"Error executing query: {e}"

    def format_result(self, result: Any) -> str:
        """Format the pandas result as a readable string."""
        if result is None:
            return "No result found."

        if isinstance(result, pd.DataFrame):
            if len(result) == 0:
                return "No matching data found."
            if len(result) > 20:
                return f"Found {len(result)} rows:\n{result.head(20).to_string()}\n... (showing first 20)"
            return result.to_string()

        if isinstance(result, pd.Series):
            if len(result) > 20:
                return f"Found {len(result)} items:\n{result.head(20).to_string()}\n... (showing first 20)"
            return result.to_string()

        if isinstance(result, (int, float)):
            if isinstance(result, float) and result == int(result):
                return str(int(result))
            return str(result)

        return str(result)

    def try_direct_query(self, sheets: Dict[str, pd.DataFrame], question: str) -> Optional[Any]:
        """Try to answer common query patterns directly without LLM.

        Returns the result if a pattern matched, None otherwise.
        """
        if not sheets:
            return None
        df = list(sheets.values())[0]
        q = question.lower()
        numeric_cols = df.select_dtypes(include='number').columns.tolist()
        text_cols = df.select_dtypes(include='object').columns.tolist()
        # Find a "name" column
        name_col = None
        for c in text_cols:
            if any(k in c.lower() for k in ['name', 'employee', 'person', 'staff']):
                name_col = c
                break
        if not name_col and text_cols:
            name_col = text_cols[-1]  # Last text column is often name

        # Pattern 1: "total/sum for [person name]"
        if name_col and numeric_cols:
            for _, row in df.iterrows():
                name_val = str(row.get(name_col, ''))
                if name_val and len(name_val) > 2:
                    # Check if this person's name (or part of it) appears in the question
                    name_parts = name_val.lower().split()
                    if any(part in q for part in name_parts if len(part) > 2):
                        if any(kw in q for kw in ['total', 'sum', 'how many', 'كم', 'مجموع']):
                            total = row[numeric_cols].sum()
                            print(f"[EXCEL_QUERY] Direct match: total for '{name_val}' = {total}")
                            return total
                        if any(kw in q for kw in ['leave', 'days', 'hours', 'إجازة']):
                            total = row[numeric_cols].sum()
                            print(f"[EXCEL_QUERY] Direct match: '{name_val}' = {total}")
                            return total

        # Pattern 2: "list all" or "show all" with "sorted/ordered"
        if name_col and numeric_cols and any(kw in q for kw in ['list all', 'show all', 'all employees', 'everyone', 'جميع']):
            totals = df[[name_col]].copy()
            totals['Total'] = df[numeric_cols].sum(axis=1)
            ascending = 'lowest' in q or 'ascending' in q or 'least' in q
            totals = totals.sort_values('Total', ascending=ascending)
            print(f"[EXCEL_QUERY] Direct match: all employees sorted")
            return totals

        # Pattern 3: "who has the most/least/highest/lowest"
        if name_col and numeric_cols and any(kw in q for kw in ['who has', 'من لديه', 'من عنده']):
            totals = df[numeric_cols].sum(axis=1)
            if any(kw in q for kw in ['most', 'highest', 'maximum', 'max', 'أكثر', 'أعلى']):
                idx = totals.idxmax()
                print(f"[EXCEL_QUERY] Direct match: max = {df.at[idx, name_col]}")
                return f"{df.at[idx, name_col]} ({int(totals[idx])})"
            if any(kw in q for kw in ['least', 'lowest', 'minimum', 'min', 'fewest', 'أقل']):
                idx = totals.idxmin()
                print(f"[EXCEL_QUERY] Direct match: min = {df.at[idx, name_col]}")
                return f"{df.at[idx, name_col]} ({int(totals[idx])})"

        # Pattern 4: "how many employees/rows/people"
        if any(kw in q for kw in ['how many employees', 'how many people', 'how many rows',
                                   'total employees', 'total people', 'count', 'عدد الموظفين']):
            if not any(kw in q for kw in ['leave', 'days', 'hours']):
                print(f"[EXCEL_QUERY] Direct match: row count = {len(df)}")
                return len(df)

        # Pattern 5: "average/mean"
        if name_col and numeric_cols and any(kw in q for kw in ['average', 'mean', 'متوسط']):
            totals = df[numeric_cols].sum(axis=1)
            avg = totals.mean()
            print(f"[EXCEL_QUERY] Direct match: average = {avg}")
            return avg

        return None

    async def generate_pandas_code_retry(self, question: str, excel_summary: str,
                                         failed_code: str, error: str) -> str:
        """Retry code generation with error feedback."""
        first_sheet = "Sheet1"
        if "=== Sheet:" in excel_summary:
            match = re.search(r"=== Sheet: (.+?) ===", excel_summary)
            if match:
                first_sheet = match.group(1)

        prompt = f"""Fix the Python pandas code that failed with an error.

{excel_summary}

QUESTION: {question}

FAILED CODE:
{failed_code}

ERROR: {error}

Generate corrected code. Output ONLY Python code, no explanations.
Use: df = sheets['{first_sheet}']
Store the answer in 'result'.
For totals across many columns, use: df.select_dtypes(include='number').sum(axis=1)

CORRECTED CODE:
df = sheets['{first_sheet}']
"""

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 500}
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    code = result.get("response", "")
                    print(f"[EXCEL_QUERY] Retry LLM response: {code[:300]}")
                    code = self._extract_code(code)
                    return code
        except Exception as e:
            print(f"[EXCEL_QUERY] Error in retry: {type(e).__name__}: {e}")
        return ""

    async def query_excel(self, file_path: str, question: str) -> Dict[str, Any]:
        """
        Main method: Answer a question about an Excel file using pandas.

        Returns:
            {
                "answer": str,  # The computed answer
                "code": str,    # The pandas code used
                "success": bool
            }
        """
        print(f"[EXCEL_QUERY] Query: {question}")
        print(f"[EXCEL_QUERY] File: {file_path}")

        # Load the Excel file
        sheets = self.load_excel(file_path)
        if not sheets:
            return {
                "answer": "Could not load the Excel file.",
                "code": "",
                "success": False
            }

        # Try direct pattern matching first (fast, no LLM needed)
        direct_result = self.try_direct_query(sheets, question)
        if direct_result is not None:
            formatted = self.format_result(direct_result)
            return {
                "answer": formatted,
                "code": "(direct pattern match)",
                "success": True
            }

        # Get summary for LLM
        summary = self.get_excel_summary(file_path)
        print(f"[EXCEL_QUERY] Summary:\n{summary[:500]}...")

        # Generate pandas code via LLM
        code = await self.generate_pandas_code(question, summary)
        print(f"[EXCEL_QUERY] Generated code:\n{code}")

        if not code:
            return {
                "answer": "Could not generate a query for this question.",
                "code": "",
                "success": False
            }

        # Execute the query
        result = self.execute_pandas_query(sheets, code)

        # If execution failed, retry once with error feedback
        if isinstance(result, str) and result.startswith("Error"):
            print(f"[EXCEL_QUERY] First attempt failed, retrying with error feedback...")
            error_msg = result.replace("Error executing query: ", "")
            retry_code = await self.generate_pandas_code_retry(question, summary, code, error_msg)
            if retry_code:
                print(f"[EXCEL_QUERY] Retry code:\n{retry_code}")
                result = self.execute_pandas_query(sheets, retry_code)
                if not (isinstance(result, str) and result.startswith("Error")):
                    code = retry_code

        # Format the result
        formatted = self.format_result(result)

        return {
            "answer": formatted,
            "code": code,
            "success": not isinstance(result, str) or not result.startswith("Error")
        }


# Singleton instance
excel_query_service = ExcelQueryService()
