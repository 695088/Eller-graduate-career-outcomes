#!/usr/bin/env python3
"""
Parse the Eller career-outcomes PDFs into structured JSON.

Each PDF is one-page major guide built from:
  * a white, bold document title on a navy banner
  * navy, bold section headings
  * bullet lists (often laid out in 2-3 columns)
  * ruled tables with a bold/white header row

The script discovers every PDF in ``pdfs of career outcomes``, extracts the
layout with pdfplumber, and writes one JSON file per PDF plus a combined
``all_career_outcomes.json``.

Usage:
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python parsing_json_pdf.py

    # Or, with pdfplumber already installed:
    python3 parsing_json_pdf.py
    python3 parsing_json_pdf.py --pdf-dir "pdfs of career outcomes" --out-dir "parsed json"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pdfplumber
except ImportError:  # pragma: no cover - friendly message for first run
    sys.exit(
        "pdfplumber is required.\n"
        "Install it with:  python3 -m pip install -r requirements.txt"
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PDF_DIR = BASE_DIR / "pdfs of career outcomes"
DEFAULT_OUT_DIR = BASE_DIR / "parsed json"

# Eller prints section headings in this navy colour.
NAVY = (0.0431, 0.188, 0.365)

BULLET_CHARS = "•▪‣·◦"

# Column headers that identify the first row of a real data table rather
# than a data row.  Two or more matches are required.
HEADER_WORDS = (
    "POSITION",
    "TITLE",
    "SAMPLE",
    "COMPANIES",
    "PRIMARY",
    "RESPONSIBILITIES",
    "JOB",
    "FUNCTION",
    "SEGMENT",
    "DESCRIPTION",
    "INDUSTRY",
    "CAREERS",
    "EDUCATION",
)

# The PDFs contain a handful of typos.  Keep the original header in
# ``original_header`` but use a clean key in the JSON.
SECTION_KEY_FIXES = {
    "COMMON INDUSTIRES": "COMMON INDUSTRIES",
    "ENGAGNEMENT": "ENGAGEMENT",
    "ENTREPRENURSHIP": "ENTREPRENEURSHIP",
    "MANAGMEMENT": "MANAGEMENT",
    "OPPORTUNITES": "OPPORTUNITIES",
    "REQUIRMENTS": "REQUIREMENTS",
}

# Small spacing fixes for text that is split oddly in the source PDFs.
TEXT_FIXES = {
    "Non- Eller": "Non-Eller",
}

MAJOR_BY_CODE = {
    "ACCT": "Accounting",
    "BMGT": "Business Management",
    "BNAD": "Business Administration",
    "ECON": "Economics",
    "ENTREPRENUERSHIP": "Entrepreneurship",
    "ENTREPRENEURSHIP": "Entrepreneurship",
    "FIN": "Finance",
    "MIS-OSCM": "Management Information Systems / Operations & Supply Chain Management",
    "MKTG": "Marketing",
}


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def clean_text(value: Optional[str]) -> str:
    """Collapse PDF line wrapping into one clean string."""
    if not value:
        return ""
    value = value.replace("\u00ad", "")  # soft hyphen
    value = value.replace("\uf0b7", "•")  # Symbol-font bullet
    # A word hyphenated across a line break should not gain a space.
    value = re.sub(r"-\s*\n\s*", "-", value)
    value = re.sub(r"\s+", " ", value)
    # PDF line wraps often insert a space around "/" ("PR/ Social Media").
    value = re.sub(r"(?<=\w)\s*/\s*(?=\w)", "/", value)
    # Normalise comma/semicolon spacing and drop PDF trailing punctuation.
    value = re.sub(r"\s*,\s*", ", ", value)
    value = re.sub(r"\s*;\s*", "; ", value)
    for bad, good in TEXT_FIXES.items():
        value = value.replace(bad, good)
    return value.strip().rstrip(",;").strip()


def normalize_key(value: str) -> str:
    """Convert a heading/column label to a stable snake_case key."""
    for bad, good in SECTION_KEY_FIXES.items():
        value = re.sub(re.escape(bad), good, value, flags=re.IGNORECASE)
    value = value.replace("&", " and ")
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value.replace(" ", "_")


def unique_key(base: str, used: Iterable[str]) -> str:
    """Return ``base`` or ``base_2``/``base_3``/... if already taken."""
    used = set(used)
    if base not in used:
        return base
    n = 2
    while f"{base}_{n}" in used:
        n += 1
    return f"{base}_{n}"


def is_navy(color: Any) -> bool:
    """Match pdfplumber colour tuples against the Eller navy."""
    if not isinstance(color, (tuple, list)) or len(color) < 3:
        return False
    return all(abs(float(a) - float(b)) < 0.02 for a, b in zip(color[:3], NAVY))


def is_white(color: Any) -> bool:
    """White is sometimes reported as grayscale ``(1.0,)``."""
    if not isinstance(color, (tuple, list)) or not color:
        return False
    return all(float(value) > 0.98 for value in color)


# ---------------------------------------------------------------------------
# Layout detection
# ---------------------------------------------------------------------------


def _group_chars_into_lines(chars: Sequence[Dict[str, Any]], tolerance: float = 2.0):
    """Group characters into visual lines (top coordinate is the key)."""
    groups: List[Dict[str, Any]] = []
    for char in sorted(chars, key=lambda c: (c["top"], c["x0"])):
        placed = False
        for group in groups:
            if abs(group["top"] - char["top"]) <= tolerance:
                group["chars"].append(char)
                group["top"] = min(group["top"], char["top"])
                group["bottom"] = max(group["bottom"], char["bottom"])
                placed = True
                break
        if not placed:
            groups.append(
                {"top": char["top"], "bottom": char["bottom"], "chars": [char]}
            )
    return sorted(groups, key=lambda g: g["top"])


def _line_text(page, group: Dict[str, Any]) -> str:
    chars = group["chars"]
    x0 = min(c["x0"] for c in chars)
    x1 = max(c["x1"] for c in chars)
    # Keep the bottom edge tight: the next line of body text can start less
    # than one point below a heading's glyph box.
    text = page.crop((x0 - 1, group["top"] - 1, x1 + 1, group["bottom"] + 0.2)).extract_text()
    return clean_text(text)


def detect_headings(page) -> List[Dict[str, Any]]:
    """Find navy, bold section headings and return their text and position."""
    chars = [
        c
        for c in page.chars
        if "Bold" in c.get("fontname", "") and is_navy(c.get("non_stroking_color"))
    ]
    headings = []
    for group in _group_chars_into_lines(chars, tolerance=2.5):
        text = _line_text(page, group)
        if not text:
            continue
        headings.append(
            {
                "header": text,
                "top": group["top"],
                "bottom": group["bottom"],
            }
        )
    return headings


def detect_title(page, first_heading_top: float) -> str:
    """Read the white, bold banner title above the first section heading."""
    chars = [
        c
        for c in page.chars
        if "Bold" in c.get("fontname", "")
        and is_white(c.get("non_stroking_color"))
        and c["top"] < first_heading_top - 1
    ]
    if not chars:
        return ""
    parts = [_line_text(page, group) for group in _group_chars_into_lines(chars)]
    return clean_text(" ".join(part for part in parts if part))


# ---------------------------------------------------------------------------
# Bullet-list parsing
# ---------------------------------------------------------------------------


def _cluster_positions(values: Sequence[float], tolerance: float = 12.0) -> List[float]:
    """Collapse nearly-identical x positions into column positions."""
    values = sorted(values)
    clusters: List[List[float]] = []
    for value in values:
        if not clusters or value - clusters[-1][-1] > tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return [sum(cluster) / len(cluster) for cluster in clusters]


def _words_to_lines(words: Sequence[Dict[str, Any]], tolerance: float = 3.0):
    """Group words into visual lines within a single column."""
    lines: List[List[Dict[str, Any]]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if not lines or abs(lines[-1][0]["top"] - word["top"]) > tolerance:
            lines.append([word])
        else:
            lines[-1].append(word)
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _line_words_text(words: Sequence[Dict[str, Any]]) -> str:
    return clean_text(" ".join(word["text"] for word in words))


def _parse_column_words(
    words: Sequence[Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """
    Turn one column of words into (subheading_lines, bullet_items).

    A bullet starts a new item.  Unbulleted lines after the first bullet are
    wrapped continuations of that item.
    """
    subheading_lines: List[str] = []
    items: List[str] = []
    current: Optional[List[str]] = None

    for line in _words_to_lines(words):
        text_parts: List[str] = []
        started_item = False

        for word in line:
            match = re.match(rf"^[{re.escape(BULLET_CHARS)}]+\s*(.*)$", word["text"])
            if match:
                # A bullet may be its own word or attached to the first word.
                if current is not None:
                    items.append(clean_text(" ".join(current)))
                current = []
                started_item = True
                if match.group(1):
                    text_parts.append(match.group(1))
            else:
                text_parts.append(word["text"])

        if text_parts:
            text = clean_text(" ".join(text_parts))
        else:
            text = ""

        if current is None:
            if text:
                subheading_lines.append(text)
            continue

        if started_item:
            # A second bullet on the same visual line starts another item.
            if text:
                current.append(text)
        elif text:
            current.append(text)

    if current is not None:
        items.append(clean_text(" ".join(current)))

    return [clean_text(line) for line in subheading_lines if clean_text(line)], [
        item for item in items if item
    ]


def parse_bullet_section(crop) -> Dict[str, Any]:
    """Parse a section crop that contains a 1-3 column bullet list."""
    words = crop.extract_words(extra_attrs=["fontname", "size"])

    # Italic text at the bottom of a list is a footnote, not a bullet item.
    italic_words = [w for w in words if "Italic" in w.get("fontname", "")]
    body_words = [w for w in words if "Italic" not in w.get("fontname", "")]

    notes: List[str] = []
    if italic_words:
        for line in _words_to_lines(italic_words, tolerance=4.0):
            text = _line_words_text(line)
            if text:
                notes.append(text)
    note = clean_text(" ".join(notes)) if notes else ""

    bullet_words = [
        w
        for w in body_words
        if re.match(rf"^[{re.escape(BULLET_CHARS)}]", w["text"])
    ]
    if not bullet_words:
        text = clean_text(crop.extract_text() or "")
        return {"type": "text", "data": text, **({"note": note} if note else {})}

    columns = _cluster_positions([w["x0"] for w in bullet_words])
    _, _, x1, _ = crop.bbox

    groups: List[Dict[str, Any]] = []
    for index, column_x in enumerate(columns):
        left = column_x - 2
        right = columns[index + 1] - 8 if index + 1 < len(columns) else x1 - 10
        column_words = [
            w for w in body_words if left <= w["x0"] < right
        ]
        subheading_lines, items = _parse_column_words(column_words)
        groups.append(
            {
                "header": clean_text(" ".join(subheading_lines)),
                "items": items,
            }
        )

    has_group_headers = any(group["header"] for group in groups)
    if has_group_headers:
        data: Any = [
            {"header": group["header"], "items": group["items"]} for group in groups
        ]
        section_type = "grouped_list"
    else:
        data = [item for group in groups for item in group["items"]]
        section_type = "list"

    result: Dict[str, Any] = {"type": section_type, "data": data}
    if note:
        result["note"] = note
    return result


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------


def _clean_table(table: Sequence[Sequence[Optional[str]]]) -> List[List[str]]:
    """Normalise a raw pdfplumber table and remove spacer rows/columns."""
    rows = [[clean_text(cell) for cell in row] for row in table]
    rows = [row for row in rows if any(row)]
    if not rows:
        return []

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]

    # pdfplumber sometimes merges an entire section (heading + table text)
    # into one giant cell in the first row.  Blank it so it does not become a
    # column/header, but leave ordinary long data cells untouched.
    if rows:
        first = rows[0]
        lengths = [len(cell) for cell in first]
        mega_index = max(range(len(first)), key=lambda i: lengths[i])
        mega_length = lengths[mega_index]
        other_max = max(
            (length for i, length in enumerate(lengths) if i != mega_index),
            default=0,
        )
        header_like = sum(
            1
            for i, cell in enumerate(first)
            if i != mega_index
            and any(word in cell.upper() for word in HEADER_WORDS)
        )
        if (
            mega_length > 250
            and mega_length > 3 * max(other_max, 1)
            and header_like >= 2
        ):
            first[mega_index] = ""

    # pdfplumber often reports empty border columns on the left/right.
    keep = [i for i in range(width) if any(row[i] for row in rows)]
    rows = [[row[i] for i in keep] for row in rows]

    # Drop phantom one-cell rows left behind by merged layout artifacts.
    while len(rows) > 1 and sum(1 for cell in rows[0] if cell) <= 1:
        rows.pop(0)

    return rows


def _looks_like_header(row: Sequence[str]) -> bool:
    score = 0
    for cell in row:
        upper = cell.upper()
        if any(word in upper for word in HEADER_WORDS):
            score += 1
    return score >= 2


def _choose_table(tables: Sequence[Sequence[Sequence[Optional[str]]]]):
    cleaned = [_clean_table(table) for table in tables]
    cleaned = [t for t in cleaned if t and max(len(row) for row in t) >= 2]
    if not cleaned:
        return None
    return max(cleaned, key=lambda t: len(t) * max(len(row) for row in t))


def _forward_fill_education(rows: List[List[str]], headers: Sequence[str]) -> None:
    """Fill merged 'EDUCATION' cells that pdfplumber only reports once."""
    for index, header in enumerate(headers):
        if "education" not in normalize_key(header):
            continue
        previous = ""
        for row in rows:
            if index < len(row):
                if row[index]:
                    previous = row[index]
                elif previous:
                    row[index] = previous


def parse_table_section(table: List[List[str]]) -> Dict[str, Any]:
    """Convert a cleaned table into header-keyed row dictionaries."""
    header_cells = table[0]
    data_rows = table[1:]

    if _looks_like_header(header_cells):
        keys: List[str] = []
        used: List[str] = []
        for cell in header_cells:
            key = normalize_key(cell) or "column"
            key = unique_key(key, used)
            used.append(key)
            keys.append(key)

        _forward_fill_education(data_rows, header_cells)

        data = []
        for row in data_rows:
            record = {
                key: (row[index] if index < len(row) else "")
                for index, key in enumerate(keys)
            }
            if any(record.values()):
                data.append(record)

        return {
            "type": "table",
            "columns": keys,
            "column_headers": dict(zip(keys, header_cells)),
            "data": data,
        }

    # Headerless two-column tables are key/value pairs (e.g. CPA requirements).
    if len(header_cells) == 2 and all(len(row) == 2 for row in table):
        data: Dict[str, str] = {}
        for row in table:
            key = normalize_key(row[0]) or "item"
            key = unique_key(key, data)
            data[key] = row[1]
        return {"type": "key_value", "data": data}

    width = max(len(row) for row in table)
    keys = [f"column_{i + 1}" for i in range(width)]
    data = [
        {key: (row[i] if i < len(row) else "") for i, key in enumerate(keys)}
        for row in table
    ]
    return {"type": "table", "columns": keys, "data": data}


# ---------------------------------------------------------------------------
# PDF parsing
# ---------------------------------------------------------------------------


def _major_from_filename(path: Path) -> Tuple[str, str]:
    code = path.stem.split("_")[0].upper()
    major = MAJOR_BY_CODE.get(code)
    if not major:
        major = code.replace("-", " ").replace("_", " ").title()
    return code, major


def parse_pdf(path: Path) -> Dict[str, Any]:
    """Parse one career-outcomes PDF into a structured document."""
    major_code, major = _major_from_filename(path)

    sections: Dict[str, Any] = {}
    section_order: List[str] = []
    title = ""

    with pdfplumber.open(path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            headings = detect_headings(page)

            if page_index == 0:
                first_top = headings[0]["top"] if headings else page.height
                title = detect_title(page, first_top) or title

            for index, heading in enumerate(headings):
                start = heading["bottom"] + 2
                end = (
                    headings[index + 1]["top"] - 2
                    if index + 1 < len(headings)
                    else page.height - 10
                )
                if end <= start:
                    continue

                crop = page.crop((0, start, page.width, end))
                table = _choose_table(crop.extract_tables())

                if table and len(table) >= 2 and max(len(row) for row in table) >= 2:
                    parsed = parse_table_section(table)
                else:
                    parsed = parse_bullet_section(crop)

                key = normalize_key(heading["header"]) or f"section_{index + 1}"
                key = unique_key(key, sections)

                parsed["original_header"] = heading["header"]
                sections[key] = parsed
                section_order.append(key)

    return {
        "major": major,
        "major_code": major_code,
        "source_file": path.name,
        "document_title": title,
        "sections": sections,
        "section_order": section_order,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse Eller career-outcomes PDFs into structured JSON."
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help=f"Folder containing the PDFs (default: {DEFAULT_PDF_DIR})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Folder for the JSON output (default: {DEFAULT_OUT_DIR})",
    )
    args = parser.parse_args()

    pdf_dir = args.pdf_dir.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()

    if not pdf_dir.is_dir():
        sys.exit(f"PDF folder not found: {pdf_dir}")

    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        sys.exit(f"No PDF files found in: {pdf_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)

    documents = []
    for pdf_path in pdf_paths:
        document = parse_pdf(pdf_path)
        documents.append(document)

        destination = out_dir / f"{pdf_path.stem}.json"
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

        print(
            f"Parsed {pdf_path.name}: "
            f"{len(document['sections'])} sections -> {destination.name}"
        )

    combined = {
        "source_folder": pdf_dir.name,
        "major_count": len(documents),
        "majors": documents,
    }
    combined_path = out_dir / "all_career_outcomes.json"
    with combined_path.open("w", encoding="utf-8") as handle:
        json.dump(combined, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(
        f"\nWrote {len(documents)} major JSON files and "
        f"{combined_path.name} to {out_dir}"
    )


if __name__ == "__main__":
    main()
