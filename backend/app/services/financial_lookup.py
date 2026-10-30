"""
Deterministic financial statement lookup.

Used when the requested figure is a line on an indexed SEC table.
The same row text the table parser emits is the source of the number.
The unit comes from that table's caption, not from a fixed "millions" label.

A fiscal-year question uses a 10-K row. A 10-Q year-to-date figure is
not substituted for the annual figure. If two different values remain
for the same company, line, and year, nothing is guessed.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.services.calculator import CalculatorError, growth_rate


_LINE_RE = re.compile(r"^([^:]+):\s*(.+)$")
_PAIR_RE = re.compile(r"(\d{4})=(-?\(?[\d,.]+\)?)")
_GROWTH_RE = re.compile(
    r"growth rate in (?P<metric>.+?) from fiscal year (?P<start>20\d{2}) "
    r"to fiscal year (?P<end>20\d{2})",
    re.IGNORECASE,
)
_CHANGE_RE = re.compile(
    r"(?:change|difference) in (?P<metric>.+?) from fiscal year "
    r"(?P<earlier>20\d{2}) to fiscal year (?P<later>20\d{2})"
    r"|did (?P<metric2>.+?) change from fiscal year "
    r"(?P<earlier2>20\d{2}) to fiscal year (?P<later2>20\d{2})",
    re.IGNORECASE,
)
_CHANGE_INTENT_RE = re.compile(r"\b(?:change|difference)\b", re.IGNORECASE)
_PERCENT_REQUEST_RE = re.compile(
    r"\b(?:percent|percentage|growth rate)\b|%",
    re.IGNORECASE,
)
_FOREIGN_CURRENCY_RE = re.compile(
    r"\b(?:euros?|eur|pounds?|gbp|yen|jpy|rupees?|inr)\b",
    re.IGNORECASE,
)
_USD_RE = re.compile(r"\b(?:usd|u\.s\. dollars?|us dollars?|dollars?)\b", re.IGNORECASE)

_SCALE = {
    "dollar": 1.0,
    "thousand": 1_000.0,
    "million": 1_000_000.0,
    "billion": 1_000_000_000.0,
}
_INCOME_ANCHORS = {"total revenue", "total net sales"}
_BALANCE_ANCHORS = {"total assets"}
# A one-letter or short numeric parenthesis is a footnote, not wording.
_FOOTNOTE_RE = re.compile(r"\(([a-z]|\d{1,2})\)", re.IGNORECASE)
_BALANCE_LINE_RE = re.compile(r"\b(?:payables?|accrued|receivables?)\b")


def _parse_value(raw: str) -> float:
    raw = raw.strip()
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()").replace(",", "")
    value = float(raw)
    return -value if negative else value


def _extract_year_values(text: str) -> Dict[int, float]:
    values = {}
    for year, raw_value in _PAIR_RE.findall(text):
        try:
            values[int(year)] = _parse_value(raw_value)
        except ValueError:
            continue
    return values


def _normalize_label_text(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()

    # Share-count rows contain this phrase too. They are not EPS.
    if {"earnings", "per", "share"} <= set(tokens) and "shares" not in tokens:
        parts = []
        if "adjusted" in tokens:
            parts.append("adjusted")
        parts.extend(["earnings", "per", "share"])
        if "diluted" in tokens:
            parts.append("diluted")
        elif "basic" in tokens:
            parts.append("basic")
        return " ".join(parts)

    if tokens and tokens[-1] in {"expense", "expenses"}:
        tokens = tokens[:-1]
    return " ".join(tokens)


def _footnote_markers(label: str) -> List[str]:
    return [match.group(1).lower() for match in _FOOTNOTE_RE.finditer(label)]


def _descriptive_notes(label: str) -> List[str]:
    notes = []
    for inner in re.findall(r"\(([^)]*)\)", label):
        if re.fullmatch(r"[a-z]|\d{1,2}", inner.strip(), flags=re.IGNORECASE):
            continue
        note = _normalize_label_text(inner)
        if note:
            notes.append(note)
    return notes


def canonical_label(label: str) -> str:
    """Base statement line. Footnote markers and descriptive notes are separate."""

    text = _FOOTNOTE_RE.sub(" ", label)
    text = re.sub(r"\([^)]*\)", " ", text)
    return _normalize_label_text(text)


def label_identity(label: str) -> str:
    """Base line plus the footnote markers and descriptive notes that distinguish it."""

    base = canonical_label(label)
    parts = [base] if base else []
    parts.extend(_descriptive_notes(label))
    parts.extend(_footnote_markers(label))
    return " ".join(part for part in parts if part)


def _search_phrases(canonical: str) -> List[str]:
    phrases = [canonical]
    if canonical == "earnings per share diluted":
        phrases.append("diluted earnings per share")
    elif canonical == "earnings per share basic":
        phrases.append("basic earnings per share")
    return phrases


def _normalize_question(question: str) -> str:
    text = question.lower().replace("&", " and ").replace("'", " ")
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _phrase_in(phrase: str, question_norm: str) -> bool:
    return re.search(
        rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])",
        question_norm,
    ) is not None


def _is_fiscal_year_question(question: str) -> bool:
    lowered = question.lower()
    return any(
        marker in lowered
        for marker in ("fiscal year", "fiscal-year", "fy ", "fy20", "fy 20")
    )


def _mentioned_tickers(question: str, company_index: Optional[Dict[str, str]]) -> List[str]:
    if not company_index:
        return []

    found = []
    for ticker, name in company_index.items():
        ticker_lower = str(ticker).lower()
        if re.search(rf"\b{re.escape(ticker_lower)}\b", question.lower()):
            found.append(str(ticker).upper())
            continue
        first = str(name or "").lower().split()
        first_word = first[0] if first else ""
        if len(first_word) >= 3 and re.search(
            rf"\b{re.escape(first_word)}\b",
            question.lower(),
        ):
            found.append(str(ticker).upper())
    return found


def _is_10k(metadata: Dict) -> bool:
    form = str(metadata.get("form", "")).upper().strip()
    if form == "10-K":
        return True
    filing = str(metadata.get("filing", "")).upper()
    return "10-K" in filing or "10K" in filing


def _chunk_ticker(metadata: Dict) -> str:
    return str(metadata.get("company", "")).upper()


# One-word labels are used only when the question names one company.
# Generic words stay excluded so "total" or "cash" is not a line by itself.
_GENERIC_ONE_WORD = {
    "total",
    "net",
    "cash",
    "revenue",
    "income",
    "sales",
    "cost",
    "expense",
    "expenses",
    "other",
    "assets",
    "equity",
    "debt",
    "tax",
    "taxes",
    "liability",
    "liabilities",
}
# A date, a quarter heading, or a generic fragment is not the requested metric.
_WEAK_LABELS = {"investments", "issued", "program"}
_QUARTER_LABEL_RE = re.compile(
    r"^(?:(?:first|second|third|fourth|1st|2nd|3rd|4th)\s+quarter|q[1-4])$"
)


def _iter_rows(table_chunks: List[Dict], allow_one_word: bool = False):
    for document in table_chunks:
        text = document.get("text", "")
        for line in text.splitlines():
            match = _LINE_RE.match(line.strip())
            if not match:
                continue
            label = match.group(1).strip()
            values = _extract_year_values(match.group(2))
            if not values:
                continue
            base = canonical_label(label)
            words = base.split()
            if len(words) < 2 and not (
                allow_one_word and words and words[0] not in _GENERIC_ONE_WORD
            ):
                continue
            yield {
                "label": label,
                "canonical": label_identity(label),
                "base": base,
                "values": values,
                "line": line.strip(),
                "document": document,
                "text": text,
            }


def _is_weak_label(canonical: str) -> bool:
    if not canonical or canonical.isdigit():
        return True
    if canonical in _WEAK_LABELS or _QUARTER_LABEL_RE.match(canonical):
        return True
    return False


def _label_names_a_change(label: Optional[str]) -> bool:
    """True when the statement line itself is a change, not a two-year difference."""

    return bool(label) and _CHANGE_INTENT_RE.search(label) is not None


def _requested_label(question_norm: str, rows: List[Dict]) -> Optional[str]:
    found = []
    seen = set()
    for row in rows:
        base = row.get("base") or row["canonical"]
        if not base or _is_weak_label(base):
            continue
        identity = row["canonical"]
        for phrase in _search_phrases(base):
            key = (len(phrase), base)
            if key in seen:
                continue
            if _phrase_in(phrase, question_norm):
                seen.add(key)
                found.append(key)
                break
        if identity != base and not _is_weak_label(identity):
            key = (len(identity), identity)
            if key not in seen and _phrase_in(identity, question_norm):
                seen.add(key)
                found.append(key)
    if not found:
        return None
    found.sort(reverse=True)
    best_length = found[0][0]
    top = {label for length, label in found if length == best_length}
    if len(top) != 1:
        return ""
    return next(iter(top))


def _row_matches_requested(row: Dict, requested: str) -> bool:
    """A base request includes every footnote or descriptive variant of that line."""

    if row["canonical"] == requested:
        return True
    return (row.get("base") or row["canonical"]) == requested


def _chunk_canonicals(text: str) -> set:
    labels = set()
    for line in text.splitlines():
        match = _LINE_RE.match(line.strip())
        if match:
            labels.add(canonical_label(match.group(1)))
    return labels


def _uses_balance_sheet(requested: str) -> bool:
    return (
        requested in _BALANCE_ANCHORS
        or "asset" in requested
        or "unearned" in requested
        or "liabilit" in requested
        or _BALANCE_LINE_RE.search(requested) is not None
    )


def _narrow_to_statement(rows: List[Dict], requested: str) -> List[Dict]:
    """Keep rows from the statement that contains this line.

    Payable, accrued, and receivable lines use a total-assets line only
    when that line is in the same table. An empty result is not a match.
    """

    anchors = _BALANCE_ANCHORS if _uses_balance_sheet(requested) else _INCOME_ANCHORS
    return [
        row
        for row in rows
        if anchors & _chunk_canonicals(row["text"])
    ]


def _absolute_change(question: str):
    """Two named fiscal years and a line, or None when this is not that question.

    A percent or growth-rate question is not an absolute change.
    """

    if _PERCENT_REQUEST_RE.search(question):
        return None
    match = _CHANGE_RE.search(question)
    if not match:
        return None
    metric = match.group("metric") or match.group("metric2")
    first = int(match.group("earlier") or match.group("earlier2"))
    second = int(match.group("later") or match.group("later2"))
    earlier, later = sorted((first, second))
    return metric, earlier, later


def _unique_rows(rows: List[Dict], key_fn) -> Optional[List[Dict]]:
    grouped: Dict = {}
    for row in rows:
        grouped.setdefault(key_fn(row), []).append(row)
    if len(grouped) != 1:
        return None
    return next(iter(grouped.values()))


def _output_unit(question: str, source_unit: Optional[str], growth: bool) -> Optional[str]:
    if growth:
        return "percent"
    lowered = question.lower()
    if source_unit == "usd_per_share":
        if re.search(r"\b(?:millions?|billions?|thousands?)\b", lowered):
            return None
        return "usd_per_share"
    if source_unit == "percent":
        if re.search(r"\b(?:millions?|billions?|thousands?|dollars?)\b", lowered):
            return None
        return "percent"
    if re.search(r"\bbillions?\b", lowered):
        return "billion"
    if re.search(r"\bmillions?\b", lowered):
        return "million"
    if re.search(r"\bthousands?\b", lowered):
        return "thousand"
    if re.search(r"\b(?:percent|percentage)\b|%", lowered):
        return None
    return source_unit


def _convert(value: float, source_unit: Optional[str], output_unit: Optional[str]) -> Optional[float]:
    if output_unit is None or source_unit is None:
        return None
    if output_unit == source_unit:
        return value
    if source_unit not in _SCALE or output_unit not in _SCALE:
        return None
    converted = value * _SCALE[source_unit] / _SCALE[output_unit]
    return round(converted, 6)


def _source_unit(row: Dict) -> Optional[str]:
    if "earnings per share" in row["canonical"] or "per share" in row["canonical"]:
        return "usd_per_share"
    scale = (row["document"].get("metadata") or {}).get("statement_scale")
    if scale == "percent":
        return "percent"
    if scale in _SCALE:
        return scale
    return None


def _prefer_annual(question: str, rows: List[Dict]) -> Optional[List[Dict]]:
    if not _is_fiscal_year_question(question):
        return rows
    annual = [
        row
        for row in rows
        if _is_10k((row["document"].get("metadata") or {}))
    ]
    if annual:
        return annual
    return None


def _select_rows(
    question: str,
    rows: List[Dict],
    requested: str,
    tickers: List[str],
) -> Optional[Dict]:
    chosen = [row for row in rows if _row_matches_requested(row, requested)]
    if not chosen:
        return None

    if len(tickers) == 1:
        ticker = tickers[0]
        company_rows = [
            row
            for row in chosen
            if _chunk_ticker(row["document"].get("metadata") or {}) == ticker
        ]
        if not company_rows:
            return {
                "status": "insufficient",
                "reason": f"no {requested} row for {ticker}",
            }
        chosen = company_rows
    elif len(tickers) > 1:
        return {
            "status": "insufficient",
            "reason": "question names more than one company",
        }

    annual = _prefer_annual(question, chosen)
    if annual is None:
        return {
            "status": "insufficient",
            "reason": "fiscal-year question has no 10-K row for this line",
        }
    return {"status": "rows", "rows": annual}


def _disambiguate_statement(rows: List[Dict], requested: str, key_fn) -> List[Dict]:
    """Use the statement anchor only among rows that disagree on the requested period.

    A table that does not contain the requested year is not evidence for it.
    An empty narrowing leaves the disagreeing rows unresolved.
    """

    if _unique_rows(rows, key_fn) is not None:
        return rows
    narrowed = _narrow_to_statement(rows, requested)
    return narrowed or rows


def resolve_table_question(
    question: str,
    table_chunks: List[Dict],
    company_index: Optional[Dict[str, str]] = None,
) -> Optional[Dict]:
    """
    Resolve one statement line, or a same-row fiscal-year growth rate.

    Returns None when the question is not a statement-line lookup.
    Returns status "insufficient" when the line was identified but the
    indexed rows do not agree. Returns status "answered" for one value.
    """

    tickers = _mentioned_tickers(question, company_index)
    rows = list(_iter_rows(table_chunks, allow_one_word=len(tickers) == 1))
    question_norm = _normalize_question(question)
    growth = _GROWTH_RE.search(question)
    change = None if growth else _absolute_change(question)
    if growth:
        label_source = _normalize_question(growth.group("metric"))
    elif change:
        label_source = _normalize_question(change[0])
    else:
        label_source = question_norm
    requested = _requested_label(label_source, rows)
    line_is_a_change = _label_names_a_change(requested if requested else None)
    unmet_change = (
        not growth
        and not change
        and not line_is_a_change
        and _CHANGE_INTENT_RE.search(question) is not None
        and _PERCENT_REQUEST_RE.search(question) is None
    )
    if requested is None:
        if change or unmet_change:
            return {
                "status": "insufficient",
                "reason": "absolute change needs one statement line and two fiscal years",
            }
        return None
    if requested == "":
        return {
            "status": "insufficient",
            "reason": "question names more than one statement line",
        }
    if _FOREIGN_CURRENCY_RE.search(question) and not _USD_RE.search(question):
        return {
            "status": "insufficient",
            "reason": "no exchange rate is available for the requested currency",
        }

    selected = _select_rows(question, rows, requested, tickers)
    if selected is None:
        if change:
            return {
                "status": "insufficient",
                "reason": f"no {requested} row for the requested company and years",
            }
        return None
    if selected["status"] == "insufficient":
        return selected

    chosen = selected["rows"]
    if growth:
        start = int(growth.group("start"))
        end = int(growth.group("end"))
        usable = [
            row
            for row in chosen
            if start in row["values"] and end in row["values"]
        ]
        if not usable:
            return {
                "status": "insufficient",
                "reason": f"{requested} does not contain both fiscal years on one row",
            }
        usable = _disambiguate_statement(
            usable,
            requested,
            lambda row: (
                round(row["values"][start], 6),
                round(row["values"][end], 6),
            ),
        )
        unique = _unique_rows(
            usable,
            lambda row: (
                round(row["values"][start], 6),
                round(row["values"][end], 6),
            ),
        )
        if unique is None:
            return {
                "status": "insufficient",
                "reason": f"more than one {requested} growth pair for {start} to {end}",
            }
        row = _best_row(unique)
        try:
            percent = round(growth_rate(row["values"][start], row["values"][end]), 2)
        except CalculatorError as exc:
            return {"status": "insufficient", "reason": str(exc)}
        return _answered(row, value=percent, unit="percent", year=end, growth={
            "start_year": start,
            "end_year": end,
            "start_value": row["values"][start],
            "end_value": row["values"][end],
        })

    if change or unmet_change:
        if not change:
            return {
                "status": "insufficient",
                "reason": "absolute change needs two named fiscal years",
            }
        _metric, earlier, later = change
        usable = [
            row
            for row in chosen
            if earlier in row["values"] and later in row["values"]
        ]
        if not usable:
            return {
                "status": "insufficient",
                "reason": f"{requested} does not contain both fiscal years on one row",
            }
        usable = _disambiguate_statement(
            usable,
            requested,
            lambda row: (
                round(row["values"][earlier], 6),
                round(row["values"][later], 6),
            ),
        )
        unique = _unique_rows(
            usable,
            lambda row: (
                round(row["values"][earlier], 6),
                round(row["values"][later], 6),
            ),
        )
        if unique is None:
            return {
                "status": "insufficient",
                "reason": f"more than one {requested} change pair for {earlier} to {later}",
            }
        units = {_source_unit(row) for row in unique}
        units.discard(None)
        if len(units) > 1:
            return {
                "status": "insufficient",
                "reason": f"conflicting units for {requested}",
            }
        row = _best_row(unique)
        source_unit = _source_unit(row)
        output_unit = _output_unit(question, source_unit, growth=False)
        converted = _convert(
            round(row["values"][later] - row["values"][earlier], 6),
            source_unit,
            output_unit,
        )
        if converted is None:
            return {
                "status": "insufficient",
                "reason": "table caption does not support the requested unit",
            }
        return _answered(
            row,
            value=converted,
            unit=output_unit,
            year=later,
            growth=None,
            change={
                "earlier_year": earlier,
                "later_year": later,
                "earlier_value": row["values"][earlier],
                "later_value": row["values"][later],
            },
        )

    years = [int(year) for year in re.findall(r"\b20\d{2}\b", question)]
    if len(years) != 1:
        return {
            "status": "insufficient",
            "reason": "statement lookup needs exactly one fiscal year",
        }
    year = years[0]
    usable = [row for row in chosen if year in row["values"]]
    if not usable:
        return {
            "status": "insufficient",
            "reason": f"{requested} has no value for {year}",
        }
    usable = _disambiguate_statement(
        usable,
        requested,
        lambda row: round(row["values"][year], 6),
    )
    unique = _unique_rows(usable, lambda row: round(row["values"][year], 6))
    if unique is None:
        return {
            "status": "insufficient",
            "reason": f"more than one {requested} value for {year}",
        }
    units = {_source_unit(row) for row in unique}
    units.discard(None)
    if len(units) > 1:
        return {
            "status": "insufficient",
            "reason": f"conflicting units for {requested}",
        }
    row = _best_row(unique)
    source_unit = _source_unit(row)
    output_unit = _output_unit(question, source_unit, growth=False)
    converted = _convert(row["values"][year], source_unit, output_unit)
    if converted is None:
        return {
            "status": "insufficient",
            "reason": "table caption does not support the requested unit",
        }
    return _answered(row, value=converted, unit=output_unit, year=year, growth=None)


def _best_row(rows: List[Dict]) -> Dict:
    def rank(row: Dict):
        metadata = row["document"].get("metadata") or {}
        return (_source_unit(row) is not None, _is_10k(metadata))

    return sorted(rows, key=rank, reverse=True)[0]


def _answered(
    row: Dict,
    value: float,
    unit: str,
    year: int,
    growth: Optional[Dict],
    change: Optional[Dict] = None,
) -> Dict:
    metadata = row["document"].get("metadata") or {}
    return {
        "status": "answered",
        "label": row["label"],
        "canonical": row["canonical"],
        "year": year,
        "value": value,
        "unit": unit,
        "line": row["line"],
        "document": row["document"],
        "source": metadata.get("source", "SEC EDGAR"),
        "filing": metadata.get("filing", "Unknown"),
        "form": metadata.get("form", "Unknown"),
        "growth": growth,
        "change": change,
    }


def format_amount(value: float) -> str:
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value)):,}"
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    whole, fraction = text.split(".")
    return f"{int(whole):,}.{fraction}"


def lookup_total_net_sales(
    question: str,
    table_chunks: List[Dict],
    company_index: Optional[Dict[str, str]] = None,
) -> Optional[Dict]:
    """Backward-compatible wrapper. Still returns nothing when the line is not total net sales."""

    result = resolve_table_question(question, table_chunks, company_index)
    if not result or result.get("status") != "answered":
        return None
    if result.get("canonical") != "total net sales":
        return None
    metadata = result["document"].get("metadata") or {}
    return {
        "metric": "total net sales",
        "year": result["year"],
        "value": result["value"],
        "unit": result["unit"],
        "document": result["document"],
        "source": metadata.get("source", "Unknown"),
        "filing": metadata.get("filing", "Unknown"),
        "form": metadata.get("form", "Unknown"),
    }
