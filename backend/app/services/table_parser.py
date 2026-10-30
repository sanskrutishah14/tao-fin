# backend/app/services/table_parser.py

"""
Table Parser

The root cause of the diluted-EPS hallucination we hit: sec_parser.py
strips all HTML and flattens tables into one bare number per line
(no column headers nearby), so a small LLM has no way to tell which
number belongs to which year/row. pandas.read_html() gives us the
table back as a structured grid instead, and this module turns each
row into one unambiguous line like:

    "Earnings per share - Diluted: 2025=7.46, 2024=6.08, 2023=6.13"

instead of 18 bare numbers with the year headers three rows up.

SEC's Inline XBRL tables render with heavy colspan/rowspan, which
pandas.read_html expands into repeated adjacent columns (the same
value copy-pasted across the merged cells). We handle that by
deduping consecutive identical cells within a row before pairing
values with years -- this generalizes reasonably well across 10-K
tables (validated: 31/54 tables in the Apple filing produced clean
output, 0 crashes) but isn't guaranteed perfect on every possible
table layout. Spot-check important numbers.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_NUMERIC_RE = re.compile(r"^-?\(?\d[\d.]*\)?$")

# Generic row labels that need their section header prefixed to stay
# unambiguous (e.g. "Basic" appears both under "Earnings per share:"
# and under "Shares used in computing earnings per share:").
_AMBIGUOUS_LABELS = {"basic", "diluted", "products", "services", "total", "domestic", "foreign"}


def _norm_cell(value) -> str | None:
    if pd.isna(value):
        return None

    s = str(value).strip()

    if s == "" or s.lower() == "nan" or s == "$":
        return None

    try:
        f = float(s.replace(",", ""))
        return str(int(f)) if f == int(f) else f"{f:g}"
    except ValueError:
        return s


def _dedupe_consecutive(values: List) -> List:
    out = []
    for v in values:
        if v is not None and (not out or v != out[-1]):
            out.append(v)
    return out


def _find_year_header(table: pd.DataFrame, max_scan: int = 10):
    """
    Scan the first few rows for the row containing the most distinct
    years (e.g. "September 27, 2025" or bare "2025") -- that's our
    column-to-year mapping for every row below it.
    """

    best_idx, best_years = None, []

    for i in range(min(max_scan, len(table))):
        raw_cells = [str(c) for c in table.iloc[i].tolist()]
        year_cells = [c for c in raw_cells if _YEAR_RE.search(c)]
        years = _dedupe_consecutive([_YEAR_RE.search(c).group(0) for c in year_cells])

        if len(years) >= 2 and len(years) > len(best_years):
            best_idx, best_years = i, years

    return best_idx, best_years


def table_to_lines(table: pd.DataFrame) -> List[str]:
    """Convert one pandas table into a list of 'label: year=value, ...' lines."""

    header_idx, years = _find_year_header(table)

    if header_idx is None:
        return []

    lines = []
    section = None

    for i in range(header_idx + 1, len(table)):
        row = _dedupe_consecutive([_norm_cell(c) for c in table.iloc[i].tolist()])

        if not row:
            continue

        label, *values = row
        numeric_values = [
            v for v in values
            if _NUMERIC_RE.match(v.replace(",", ""))
        ]

        if not numeric_values:
            # This is a section header row (e.g. "Earnings per share:")
            # with a label but no numbers -- remember it for context.
            if label and not label.replace(",", "").isdigit():
                section = label.rstrip(":")
            continue

        full_label = label
        if section and label.lower() in _AMBIGUOUS_LABELS:
            full_label = f"{section} - {label}"

        pairs = list(zip(years, numeric_values))
        if pairs:
            lines.append(
                f"{full_label}: " + ", ".join(f"{y}={v}" for y, v in pairs)
            )

    return lines


_SCALE_PATTERNS = (
    ("billion", re.compile(r"\b(?:dollars?\s+)?in\s+billions\b", re.I)),
    ("million", re.compile(r"\b(?:dollars?\s+)?in\s+millions\b", re.I)),
    ("thousand", re.compile(r"\b(?:dollars?\s+)?in\s+thousands\b", re.I)),
    ("dollar", re.compile(r"\b(?:amounts?\s+)?in\s+dollars\b|\(\s*dollars\s*\)", re.I)),
)
_XBRL_SCALE = {"0": "dollar", "3": "thousand", "6": "million", "9": "billion"}
_PERCENT_RE = re.compile(
    r"\bin\s+percent(?:ages?)?\b|\(\s*percent(?:age)?s?\s*\)",
    re.I,
)
_CAPTION_PHRASE = re.compile(
    r"\([^)]{0,260}?\bin\s+(?:millions|billions|thousands|dollars|percent(?:ages?)?)\b[^)]*\)"
    r"|\(\s*percent(?:age)?s?\s*\)"
    r"|[^\n.]{0,80}\bin\s+(?:millions|billions|thousands|dollars|percent(?:ages?)?)\b[^\n.]{0,80}",
    re.I,
)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _strip_share_exceptions(text: str) -> str:
    """Drop the share-count carve-out so it is not a second money unit."""

    cleaned = re.sub(r"except\b.{0,240}?per[- ]share amounts?", " ", text, flags=re.I)
    cleaned = re.sub(
        r"except\b.{0,240}?(?:number of )?shares?\b.{0,80}",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"shares?\s+in\s+thousands", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"net income in millions and shares in thousands", "net income in millions", cleaned, flags=re.I)
    return cleaned


def _money_scales(text: str) -> set:
    """Caption scales stated in this text. An empty set means no money unit."""

    if not text:
        return set()
    lowered = text.lower()
    if "square feet" in lowered or "square foot" in lowered:
        return {"__non_money__"}
    cleaned = _strip_share_exceptions(lowered)
    found = set()
    for scale, pattern in _SCALE_PATTERNS:
        if pattern.search(cleaned):
            found.add(scale)
    return found


def _last_caption(window: str) -> str:
    matches = list(_CAPTION_PHRASE.finditer(window or ""))
    if not matches:
        return ""
    return matches[-1].group(0)


def _preceding_text(table_tag, limit: int = 500) -> str:
    """Text after the previous table and before this one.

    A caption belongs to the table it introduces. The walk stops at the
    previous table, so that table's caption is not reused here.
    """

    texts = []
    node = table_tag
    while node is not None and getattr(node, "name", None) not in ("body", "html", "[document]"):
        prev = node.previous_sibling
        while prev is not None:
            if isinstance(prev, Tag) and (
                prev.name == "table" or prev.find("table") is not None
            ):
                return _collapse(" ".join(reversed(texts)))[-limit:]
            snippet = prev.get_text(" ", strip=True) if isinstance(prev, Tag) else str(prev)
            snippet = _collapse(snippet)
            if snippet:
                texts.append(snippet)
                if sum(len(item) for item in texts) > limit:
                    return _collapse(" ".join(reversed(texts)))[-limit:]
            prev = prev.previous_sibling
        node = getattr(node, "parent", None)
    return _collapse(" ".join(reversed(texts)))[-limit:]


def _inside_blob(table: pd.DataFrame) -> str:
    """Header window for this table, through its year row when that row sits lower."""

    parts = [" ".join(str(column) for column in table.columns)]
    if len(table) == 0:
        return _collapse(" ".join(parts)).lower()
    header_idx, _years = _find_year_header(table)
    last = 3
    if header_idx is not None:
        last = max(last, header_idx)
    last = min(last, 9, len(table) - 1)
    for index in range(last + 1):
        parts.append(" ".join(str(cell) for cell in table.iloc[index].tolist()))
    return _collapse(" ".join(parts)).lower()


def _xbrl_money_scale(table_tag) -> Optional[str]:
    """One USD scale from this table's own facts. Mixed scales are not a scale."""

    if table_tag is None:
        return None
    found = set()
    for tag in table_tag.find_all(True):
        scale = tag.get("scale")
        if scale not in _XBRL_SCALE:
            continue
        unit = str(tag.get("unitref") or "")
        if "usd" not in unit.lower():
            continue
        found.add(_XBRL_SCALE[scale])
    if len(found) == 1:
        return next(iter(found))
    return None


def _choose_scale(text_scales: set, xbrl_scale: Optional[str]) -> Optional[str]:
    if "__non_money__" in text_scales:
        return None
    stated = {scale for scale in text_scales if scale != "__non_money__"}
    if len(stated) > 1:
        return None
    caption_scale = next(iter(stated)) if stated else None
    if caption_scale and xbrl_scale and caption_scale != xbrl_scale:
        return None
    return caption_scale or xbrl_scale


def _table_scale(table: pd.DataFrame, preceding_text: str = "", table_tag=None) -> Dict:
    """Read the unit caption for this table only. Row text is unchanged."""

    inside = _money_scales(_inside_blob(table))
    if table_tag is not None:
        inside |= _money_scales(_tag_head(table_tag, table))
    outside = _money_scales(_last_caption(preceding_text))
    blob = _inside_blob(table) + " " + _last_caption(preceding_text).lower()
    per_share = "per share" in blob or "per-share" in blob
    stated = inside | outside
    scale = _choose_scale(stated, _xbrl_money_scale(table_tag))
    money_present = any(item != "__non_money__" for item in stated) or bool(
        _xbrl_money_scale(table_tag)
    )
    # A percent caption is a unit only when this table does not also state a money unit.
    if (
        scale is None
        and not money_present
        and "__non_money__" not in stated
        and _PERCENT_RE.search(blob)
    ):
        scale = "percent"
    return {
        "statement_scale": scale,
        "per_share_in_caption": per_share,
    }


def _tag_head(table_tag, table: pd.DataFrame | None = None) -> str:
    """Caption text for this table's header, not a note further down the table."""

    text = _collapse(table_tag.get_text(" ", strip=True))
    if table is not None:
        _header_idx, years = _find_year_header(table)
        ends = []
        for year in years:
            match = re.search(rf"\b{year}\b", text)
            if match:
                ends.append(match.end())
        if ends:
            return text[: max(ends) + 40].lower()
    return text[:400].lower()


def _frame_tokens(table: pd.DataFrame) -> List[str]:
    tokens = []
    for value in table.fillna("").astype(str).values.flatten():
        token = _collapse(value)
        if not token or token.lower() == "nan":
            continue
        digits = re.sub(r"[^0-9]", "", token)
        if len(digits) >= 3 or re.search(r"[A-Za-z]", token):
            tokens.append(token)
        if len(tokens) >= 6:
            break
    return tokens


def _tag_matches(table_tag, tokens: List[str]) -> bool:
    text = _collapse(table_tag.get_text(" ", strip=True))
    digits = re.sub(r"[^0-9]", "", text)
    hits = 0
    for token in tokens:
        token_digits = re.sub(r"[^0-9]", "", token)
        if token_digits and token_digits in digits:
            hits += 1
        elif token.lower() in text.lower():
            hits += 1
    return hits >= min(2, len(tokens))


def _align_table_tags(frames: List[pd.DataFrame], html: str) -> List[Optional[object]]:
    soup = BeautifulSoup(html, "lxml")
    tags = soup.find_all("table")
    aligned = []
    cursor = 0
    for frame in frames:
        tokens = _frame_tokens(frame)
        match = None
        for index in range(cursor, len(tags)):
            if tokens and _tag_matches(tags[index], tokens):
                match = tags[index]
                cursor = index + 1
                break
        aligned.append(match)
    return aligned


def extract_table_chunks(html_path: str, metadata: Dict | None = None) -> List[Dict]:
    """
    Parse every table in a filing's HTML into RAG-ready chunk dicts,
    same shape as chunker.split_into_chunks() output, so they can be
    embedded and added to the vector store alongside narrative text.
    """

    try:
        html = Path(html_path).read_text(encoding="utf-8", errors="replace")
        tables = pd.read_html(html_path)
    except ValueError:
        # No tables found in the document.
        return []

    tags = _align_table_tags(tables, html)
    chunks = []

    for table_index, table in enumerate(tables):
        lines = table_to_lines(table)

        if not lines:
            continue

        table_tag = tags[table_index] if table_index < len(tags) else None
        preceding = _preceding_text(table_tag) if table_tag is not None else ""
        chunk_metadata = {
            "type": "table",
            "table_index": table_index,
            **_table_scale(table, preceding, table_tag),
        }
        if metadata:
            chunk_metadata.update(metadata)

        chunks.append({
            "text": "\n".join(lines),
            "metadata": chunk_metadata,
        })

    return chunks