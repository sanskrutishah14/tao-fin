"""Build the 150-question development set from filings already on disk.

Gold values are read from parsed 10-K lines or from a sentence in the
filing text. A figure that cannot be found is omitted. Nothing here
changes the answering pipeline or the scorer.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "validation_150_questions.json"
SEC_DIR = BACKEND_DIR / "data" / "sec"

for _path in (PROJECT_ROOT, BACKEND_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from app.services.calculator import CalculatorError, growth_rate  # noqa: E402
from app.services.financial_lookup import (  # noqa: E402
    _convert,
    _extract_year_values,
    _normalize_question,
    _phrase_in,
    canonical_label,
    resolve_table_question,
)
from app.services.metrics_resolver import resolve as resolve_metric  # noqa: E402
from app.services.table_parser import extract_table_chunks  # noqa: E402


LABEL = (
    "150-question development set drawn from the four companies' filings "
    "already on disk. Questions are not copied from the smoke test, the "
    "12-question validation set, or the 50-question development set. "
    "Not an independent holdout and not an estimate of overall financial accuracy."
)

FILINGS = {
    "AAPL": {
        "company": "Apple Inc.",
        "ask": "Apple",
        "cik": "0000320193",
        "form": "10-K",
        "accession": "0000320193-25-000079",
        "report_date": "2025-09-27",
        "html": "AAPL_10-K_000032019325000079.html",
        "text": "AAPL_10-K_000032019325000079.txt",
    },
    "MSFT": {
        "company": "Microsoft Corporation",
        "ask": "Microsoft",
        "cik": "0000789019",
        "form": "10-K",
        "accession": "0001193125-26-323660",
        "report_date": "2026-06-30",
        "html": "MSFT_10-K_000119312526323660.html",
        "text": "MSFT_10-K_000119312526323660.txt",
    },
    "TROW": {
        "company": "T. Rowe Price Group, Inc.",
        "ask": "TROW",
        "cik": "0001113169",
        "form": "10-K",
        "accession": "0001628280-26-008002",
        "report_date": "2025-12-31",
        "html": "TROW_10-K_000162828026008002.html",
        "text": "TROW_10-K_000162828026008002.txt",
    },
    "VENU": {
        "company": "Venu Holding Corporation",
        "ask": "Venu",
        "cik": "0001770501",
        "form": "10-K",
        "accession": "0001493152-26-014137",
        "report_date": "2025-12-31",
        "html": "VENU_10-K_000149315226014137.html",
        "text": "VENU_10-K_000149315226014137.txt",
    },
}

COMPANY_INDEX = {ticker: meta["company"] for ticker, meta in FILINGS.items()}
WORD_LABEL = re.compile(r"^[a-z]+(?: [a-z]+){1,7}$")
DENY = {
    "current year",
    "first quarter",
    "second quarter",
    "third quarter",
    "fourth quarter",
    "prior years",
    "u s",
    "united kingdom",
    "greater china",
    "other countries",
    "rest of asia pacific",
    "all other jurisdictions",
    "total net",
    "total operating",
    "federal total",
    "foreign total",
    "state total",
    "state and local",
    "other changes",
    "balances at end of period",
}
RATIO_WORDS = ("gross margin", "operating margin", "net margin", "profit margin")
UNIT_WORD = {
    "million": "millions",
    "billion": "billions",
    "thousand": "thousands",
    "dollar": "dollars",
    "percent": "percent",
}
NARRATIVE_SPECS = [
    {
        "ticker": "AAPL",
        "question": (
            "During the fourth quarter of 2025, how many USD billions of "
            "Apple's May 2024 share repurchase program were utilized?"
        ),
        "quote": (
            "During the fourth quarter of 2025, the Company utilized the "
            "final $19.8 billion under the May 2024 program."
        ),
        "value": 19.8,
        "unit": "billion",
    },
    {
        "ticker": "AAPL",
        "question": (
            "As of September 27, 2025, how many USD millions of Apple's "
            "May 2025 share repurchase program had been utilized?"
        ),
        "quote": "As of September 27, 2025, $221 million of the May 2025 program had been utilized.",
        "value": 221.0,
        "unit": "million",
    },
    {
        "ticker": "AAPL",
        "question": (
            "As of September 27, 2025, what were Apple's fixed payment "
            "obligations under additional leases that had not yet commenced, "
            "in USD millions?"
        ),
        "quote": (
            "As of September 27, 2025, the Company had $ 523 million of "
            "fixed payment obligations under additional leases"
        ),
        "value": 523.0,
        "unit": "million",
    },
    {
        "ticker": "MSFT",
        "question": (
            "How many USD billions did Microsoft return to shareholders "
            "through share repurchases and dividends in the fourth quarter "
            "of fiscal year 2026?"
        ),
        "quote": (
            "We returned $10.2 billion to shareholders in the form of "
            "share repurchases and dividends in the fourth quarter of fiscal year 2026."
        ),
        "value": 10.2,
        "unit": "billion",
    },
    {
        "ticker": "MSFT",
        "question": (
            "By how many USD billions did gains from investments in OpenAI "
            "increase Microsoft's fiscal year 2026 net income?"
        ),
        "quote": (
            "net gains from investments in OpenAI, which resulted in an "
            "increase in net income and diluted EPS of $5.0 billion and $0.67"
        ),
        "value": 5.0,
        "unit": "billion",
    },
    {
        "ticker": "TROW",
        "question": (
            "At December 31, 2025, how many USD billions of seed capital "
            "investments in its products did TROW have?"
        ),
        "quote": "At December 31, 2025, we had seed capital investments in our products of $1.1 billion.",
        "value": 1.1,
        "unit": "billion",
    },
    {
        "ticker": "TROW",
        "question": (
            "At December 31, 2025, how many USD billions of co-investments did TROW report?"
        ),
        "quote": "These investments are commonly referred to as co-investments and totaled $0.3 billion at December 31, 2025.",
        "value": 0.3,
        "unit": "billion",
    },
    {
        "ticker": "VENU",
        "question": (
            "What was the aggregate purchase amount of Venu's Series B "
            "preferred stock issued to Aramark on June 16, 2025, in USD millions?"
        ),
        "quote": "with an aggregate purchase amount of $ 10.125 million",
        "value": 10.125,
        "unit": "million",
    },
]


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _load_existing_questions() -> List[str]:
    names = (
        "smoke_questions.json",
        "validation_questions.json",
        "validation_50_questions.json",
    )
    found = []
    for name in names:
        payload = json.loads((PROJECT_ROOT / "evaluation" / name).read_text(encoding="utf-8"))
        found.extend(_normalize_question(item["question"]) for item in payload)
    return found


def _blocked(ask: str, canonical: str, year: int, existing: Sequence[str]) -> bool:
    for question in existing:
        if str(year) not in question or ask.lower() not in question:
            continue
        if _phrase_in(canonical, question):
            return True
    return False


def _quote_for(document: str, value: float) -> Optional[str]:
    """Find the displayed number, not a shorter digit sequence inside it."""

    if value <= 0:
        return None
    collapsed = _collapse(document)
    texts = []
    if float(value) == int(value):
        whole = int(value)
        texts.extend([f"{whole:,}", str(whole)])
    rendered = f"{value:.6f}".rstrip("0").rstrip(".")
    if "." in rendered:
        whole, frac = rendered.split(".", 1)
        texts.append(f"{int(whole):,}.{frac}")
        texts.append(rendered)
    for candidate in texts:
        if not candidate:
            continue
        if re.search(rf"(?<![\d,.]){re.escape(candidate)}(?![\d,.])", collapsed):
            return candidate
    return None


def _base(ticker: str, year: int, category: str) -> Dict[str, Any]:
    meta = FILINGS[ticker]
    return {
        "ticker": ticker,
        "cik": meta["cik"],
        "company": meta["company"],
        "form": meta["form"],
        "fiscal_year": year,
        "accession": meta["accession"],
        "report_date": meta["report_date"],
        "source_file": f"backend/data/sec/{meta['html']}",
        "category": category,
        "expected_path": "not used for scoring",
        "answer_mode": "numeric",
        "tolerance_mode": "exact",
        "tolerance_abs": 0,
    }


def _acceptable_label(canonical: str) -> bool:
    if not WORD_LABEL.match(canonical) or canonical in DENY:
        return False
    if any(word in canonical for word in ("beginning", "issuance", "reclassified", "footnote")):
        return False
    if "per share" in canonical or "earnings per share" in canonical:
        return False
    if any(phrase in canonical for phrase in RATIO_WORDS):
        return False
    return True


def _longest_match(question: str, canonicals: Sequence[str]) -> Optional[str]:
    normalized = _normalize_question(question)
    found = []
    for canonical in canonicals:
        if canonical and _phrase_in(canonical, normalized):
            found.append(canonical)
    if not found:
        return None
    found.sort(key=len, reverse=True)
    if len(found) > 1 and len(found[0]) == len(found[1]):
        return ""
    return found[0]


def _parse_filings() -> Tuple[Dict[str, List[Dict]], Dict[str, str], Dict[str, str], List[str]]:
    chunks: Dict[str, List[Dict]] = {}
    html: Dict[str, str] = {}
    text: Dict[str, str] = {}
    canonicals = set()
    for ticker, meta in FILINGS.items():
        html_path = SEC_DIR / meta["html"]
        parsed = extract_table_chunks(
            str(html_path),
            metadata={
                "company": ticker,
                "form": "10-K",
                "filing": meta["html"],
                "source": "SEC EDGAR",
            },
        )
        chunks[ticker] = parsed
        html[ticker] = html_path.read_text(encoding="utf-8", errors="replace")
        text[ticker] = (SEC_DIR / meta["text"]).read_text(encoding="utf-8", errors="replace")
        for chunk in parsed:
            for line in chunk.get("text", "").splitlines():
                if ":" not in line:
                    continue
                canonicals.add(canonical_label(line.split(":", 1)[0]))
    return chunks, html, text, sorted(canonicals)


def _rows_for(chunks: List[Dict]) -> List[Dict[str, Any]]:
    rows = []
    for chunk in chunks:
        scale = (chunk.get("metadata") or {}).get("statement_scale")
        for line in chunk.get("text", "").splitlines():
            if ":" not in line:
                continue
            label, rest = line.split(":", 1)
            values = _extract_year_values(rest)
            if not values:
                continue
            canonical = canonical_label(label)
            rows.append({
                "label": label.strip(),
                "canonical": canonical,
                "scale": scale,
                "values": values,
                "line": line.strip(),
            })
    return rows


def _unique_year(rows: List[Dict], canonical: str, year: int) -> Optional[Dict]:
    chosen = [
        row for row in rows
        if row["canonical"] == canonical and year in row["values"] and row["values"][year] > 0
    ]
    if not chosen:
        return None
    signatures = {
        (round(row["values"][year], 6), row["scale"])
        for row in chosen
        if row["scale"] in UNIT_WORD
    }
    if len(signatures) != 1:
        return None
    value, scale = next(iter(signatures))
    sample = next(row for row in chosen if row["scale"] == scale)
    return {"value": value, "scale": scale, "line": sample["line"], "label": sample["label"]}


def _lookup_question(ask: str, canonical: str, year: int, scale: str) -> str:
    if scale == "percent":
        return f"What was {ask}'s {canonical} for fiscal year {year}, in percent?"
    return (
        f"What was {ask}'s {canonical} for fiscal year {year}, "
        f"in USD {UNIT_WORD[scale]}?"
    )


def _take(pool: List[Dict], count: int) -> List[Dict]:
    buckets: Dict[str, List[Dict]] = {ticker: [] for ticker in FILINGS}
    seen = set()
    ordered = sorted(pool, key=lambda item: (item["canonical"], -item["year"]))
    for item in ordered:
        key = (item["ticker"], item["canonical"])
        if key in seen:
            continue
        seen.add(key)
        buckets[item["ticker"]].append(item)
    picked = []
    while len(picked) < count and any(buckets.values()):
        for ticker in FILINGS:
            if not buckets[ticker]:
                continue
            picked.append(buckets[ticker].pop(0))
            if len(picked) >= count:
                break
    return picked


def _line_with_value(rows: List[Dict], year: int, value: float) -> Optional[str]:
    rendered = f"{value:.6f}".rstrip("0").rstrip(".")
    needles = [f"{year}={rendered}"]
    if float(value) == int(value):
        needles.append(f"{year}={int(value)}")
    for row in rows:
        if year in row["values"] and round(row["values"][year], 6) == round(value, 6):
            if any(needle in row["line"] for needle in needles):
                return row["line"]
    return None


def build_questions() -> Tuple[List[Dict[str, Any]], str]:
    existing = _load_existing_questions()
    chunks, html, prose, canonicals = _parse_filings()
    all_chunks = [chunk for group in chunks.values() for chunk in group]
    rows = {ticker: _rows_for(group) for ticker, group in chunks.items()}
    questions: List[Dict[str, Any]] = []
    limitation = ""

    facts = []
    for ticker, meta in FILINGS.items():
        for row in rows[ticker]:
            if not _acceptable_label(row["canonical"]):
                continue
            for year, value in row["values"].items():
                if year < 2018 or year > 2026 or value <= 0:
                    continue
                unique = _unique_year(rows[ticker], row["canonical"], year)
                if unique is None or unique["scale"] == "dollar" or unique["line"] != row["line"]:
                    continue
                if _blocked(meta["ask"], row["canonical"], year, existing):
                    continue
                quote = _quote_for(html[ticker], unique["value"])
                if quote is None:
                    continue
                question = _lookup_question(meta["ask"], row["canonical"], year, unique["scale"])
                if _normalize_question(question) in existing:
                    continue
                if _longest_match(question, canonicals) != row["canonical"]:
                    continue
                facts.append({
                    "ticker": ticker,
                    "year": year,
                    "canonical": row["canonical"],
                    "value": unique["value"],
                    "scale": unique["scale"],
                    "line": unique["line"],
                    "quote": quote,
                    "question": question,
                })
                break

    lookups = _take(facts, 90)
    used = {(item["ticker"], item["canonical"], item["year"]) for item in lookups}
    for item in lookups:
        record = _base(item["ticker"], item["year"], "lookup")
        record.update({
            "statement": "10-K table",
            "question": item["question"],
            "line_item": item["canonical"],
            "source_quote": item["quote"],
            "source_line": item["line"],
            "gold_value": item["value"],
            "gold_unit": "usd_per_share" if item["scale"] == "per_share" else item["scale"],
            "allow_scale_conversion": item["scale"] in {"million", "billion", "thousand", "dollar"},
        })
        questions.append(record)

    conversions = []
    for item in facts:
        key = (item["ticker"], item["canonical"], item["year"])
        if key in used or item["scale"] != "million" or item["value"] < 1000:
            continue
        converted = _convert(item["value"], "million", "billion")
        if converted is None:
            continue
        question = _lookup_question(FILINGS[item["ticker"]]["ask"], item["canonical"], item["year"], "billion")
        if _normalize_question(question) in existing or _longest_match(question, canonicals) != item["canonical"]:
            continue
        conversions.append({**item, "question": question, "converted": converted})
    for item in _take(conversions, 14):
        record = _base(item["ticker"], item["year"], "unit_conversion")
        record.update({
            "statement": "10-K table",
            "question": item["question"],
            "line_item": item["canonical"],
            "source_quote": item["quote"],
            "source_line": item["line"],
            "gold_value": item["converted"],
            "gold_unit": "billion",
            "allow_scale_conversion": True,
            "inputs": {
                "source_value": item["value"],
                "source_unit": "million",
                "formula": f"{item['value']} million = {item['converted']} billion",
            },
        })
        questions.append(record)
        used.add((item["ticker"], item["canonical"], item["year"]))

    ratios = []
    for ticker, meta in FILINGS.items():
        for metric in ("gross margin", "operating margin", "net margin"):
            for year in (2026, 2025, 2024, 2023):
                question = f"What was {meta['ask']}'s {metric} for fiscal year {year}?"
                if _normalize_question(question) in existing or _blocked(meta["ask"], metric, year, existing):
                    continue
                found = resolve_metric(question, [str(year)], chunks[ticker])
                if not found or found.get("computed_value_pct") is None:
                    continue
                numerator = _line_with_value(rows[ticker], year, found["numerator_value"])
                denominator = _line_with_value(rows[ticker], year, found["denominator_value"])
                quote = _quote_for(html[ticker], found["numerator_value"])
                if not numerator or not denominator or quote is None:
                    continue
                ratios.append({
                    "ticker": ticker,
                    "year": year,
                    "question": question,
                    "metric": metric,
                    "gold": found["computed_value_pct"],
                    "numerator": found["numerator_value"],
                    "denominator": found["denominator_value"],
                    "numerator_line": numerator,
                    "denominator_line": denominator,
                    "quote": quote,
                })
    for item in ratios[:8]:
        record = _base(item["ticker"], item["year"], "ratio")
        record.update({
            "statement": "10-K table",
            "question": item["question"],
            "line_item": item["metric"],
            "source_quote": item["quote"],
            "source_line": item["numerator_line"],
            "source_line_extra": item["denominator_line"],
            "gold_value": item["gold"],
            "gold_unit": "percent",
            "allow_scale_conversion": False,
            "tolerance_mode": "absolute",
            "tolerance_abs": 0.01,
            "inputs": {
                "numerator": item["numerator"],
                "denominator": item["denominator"],
                "formula": (
                    f"round({item['numerator']} / {item['denominator']} * 100, 2)"
                ),
            },
        })
        questions.append(record)

    pairs = []
    for ticker, meta in FILINGS.items():
        grouped: Dict[str, List[Dict]] = {}
        for row in rows[ticker]:
            if not _acceptable_label(row["canonical"]) or row["scale"] not in {"million", "thousand"}:
                continue
            grouped.setdefault(row["canonical"], []).append(row)
        for canonical, group in grouped.items():
            usable = []
            for row in group:
                years = sorted(year for year in row["values"] if 2018 <= year <= 2026)
                if len(years) < 2:
                    continue
                earlier, later = years[-2], years[-1]
                if row["values"][earlier] == 0 or row["values"][later] <= 0 or row["values"][earlier] <= 0:
                    continue
                usable.append((row, earlier, later))
            if not usable:
                continue
            signatures = {
                (
                    round(row["values"][earlier], 6),
                    round(row["values"][later], 6),
                    row["scale"],
                )
                for row, earlier, later in usable
            }
            if len(signatures) != 1:
                continue
            row, earlier, later = usable[0]
            if (ticker, canonical, later) in used:
                continue
            if _blocked(meta["ask"], canonical, earlier, existing) and _blocked(meta["ask"], canonical, later, existing):
                continue
            quote = _quote_for(html[ticker], row["values"][later])
            if quote is None:
                continue
            try:
                percent = round(growth_rate(row["values"][earlier], row["values"][later]), 2)
            except CalculatorError:
                continue
            growth_question = (
                f"What was the growth rate in {meta['ask']}'s {canonical} "
                f"from fiscal year {earlier} to fiscal year {later}, in percent?"
            )
            change_question = (
                f"By how many USD {UNIT_WORD[row['scale']]} did {meta['ask']}'s {canonical} "
                f"change from fiscal year {earlier} to fiscal year {later}?"
            )
            if _longest_match(growth_question, canonicals) != canonical:
                continue
            pairs.append({
                "ticker": ticker,
                "canonical": canonical,
                "year": later,
                "earlier": earlier,
                "later": later,
                "scale": row["scale"],
                "start": row["values"][earlier],
                "end": row["values"][later],
                "line": row["line"],
                "quote": quote,
                "percent": percent,
                "delta": round(row["values"][later] - row["values"][earlier], 6),
                "growth_question": growth_question,
                "change_question": change_question,
            })

    growth_items = _take(pairs, 12)
    growth_keys = {(item["ticker"], item["canonical"]) for item in growth_items}
    change_pool = [item for item in pairs if (item["ticker"], item["canonical"]) not in growth_keys]
    change_items = _take(change_pool, 10)
    for item in growth_items:
        if _normalize_question(item["growth_question"]) in existing:
            continue
        record = _base(item["ticker"], item["later"], "growth")
        record.update({
            "statement": "10-K table",
            "question": item["growth_question"],
            "line_item": item["canonical"],
            "source_quote": item["quote"],
            "source_line": item["line"],
            "gold_value": item["percent"],
            "gold_unit": "percent",
            "allow_scale_conversion": False,
            "tolerance_mode": "absolute",
            "tolerance_abs": 0.01,
            "inputs": {
                "start_year": item["earlier"],
                "end_year": item["later"],
                "start_value": item["start"],
                "end_value": item["end"],
                "formula": (
                    f"round(({item['end']} - {item['start']}) / {item['start']} * 100, 2)"
                ),
            },
        })
        questions.append(record)
    for item in change_items:
        if _normalize_question(item["change_question"]) in existing:
            continue
        record = _base(item["ticker"], item["later"], "comparison")
        record.update({
            "statement": "10-K table",
            "question": item["change_question"],
            "line_item": item["canonical"],
            "source_quote": item["quote"],
            "source_line": item["line"],
            "gold_value": item["delta"],
            "gold_unit": item["scale"],
            "allow_scale_conversion": True,
            "inputs": {
                "earlier_year": item["earlier"],
                "later_year": item["later"],
                "earlier_value": item["start"],
                "later_value": item["end"],
                "formula": f"{item['end']} - {item['start']}",
            },
        })
        questions.append(record)

    absent_specs = [
        ("AAPL", 2025, "investment advisory fees"),
        ("MSFT", 2026, "investment advisory fees"),
        ("TROW", 2025, "cost of sales products"),
        ("VENU", 2025, "commercial paper"),
    ]
    for ticker, year, canonical in absent_specs:
        if any(row["canonical"] == canonical for row in rows[ticker]):
            continue
        question = (
            f"What was {FILINGS[ticker]['ask']}'s {canonical} for fiscal year {year}, "
            "in USD millions?"
        )
        outcome = resolve_table_question(question, all_chunks, COMPANY_INDEX)
        if not outcome or outcome.get("status") != "insufficient":
            continue
        record = _base(ticker, year, "insufficient_evidence")
        record.update({
            "statement": "absent from this company's 10-K tables",
            "question": question,
            "line_item": canonical,
            "source_quote": FILINGS[ticker]["company"],
            "gold_value": None,
            "gold_text": "Insufficient evidence.",
            "gold_unit": "million",
            "allow_scale_conversion": False,
            "expected_answer": "abstain",
            "evidence_note": (
                f"{FILINGS[ticker]['company']} {FILINGS[ticker]['html']} "
                f"has no {canonical} line for {year}."
            ),
        })
        questions.append(record)

    unscaled = []
    for row in rows["VENU"]:
        if row["scale"] is not None or not _acceptable_label(row["canonical"]):
            continue
        years = [year for year, value in row["values"].items() if 2018 <= year <= 2026 and value > 0]
        if len(years) != 1:
            continue
        year = years[0]
        same = [
            other for other in rows["VENU"]
            if other["canonical"] == row["canonical"] and year in other["values"]
        ]
        values = {round(other["values"][year], 6) for other in same}
        if len(values) != 1:
            continue
        quote = _quote_for(html["VENU"], row["values"][year])
        if quote is None:
            continue
        question = (
            f"What was Venu's {row['canonical']} for fiscal year {year}, in USD millions?"
        )
        if _normalize_question(question) in existing:
            continue
        outcome = resolve_table_question(question, all_chunks, COMPANY_INDEX)
        if not outcome or outcome.get("status") != "insufficient":
            continue
        unscaled.append((year, row, quote, question))
    for year, row, quote, question in unscaled[:4]:
        record = _base("VENU", year, "insufficient_evidence")
        record.update({
            "statement": "10-K table without a stated money scale",
            "question": question,
            "line_item": row["canonical"],
            "source_quote": quote,
            "source_line": row["line"],
            "gold_value": None,
            "gold_text": "Insufficient evidence.",
            "gold_unit": "million",
            "allow_scale_conversion": False,
            "expected_answer": "abstain",
            "evidence_note": "The parsed line has no caption or XBRL money scale, so the million unit is not supported.",
        })
        questions.append(record)

    for spec in NARRATIVE_SPECS:
        ticker = spec["ticker"]
        collapsed = _collapse(prose[ticker])
        if _collapse(spec["quote"]) not in collapsed:
            continue
        if _normalize_question(spec["question"]) in existing:
            continue
        record = _base(ticker, int(FILINGS[ticker]["report_date"][:4]), "narrative")
        record["fiscal_year"] = int(FILINGS[ticker]["report_date"][:4])
        record["source_file"] = f"backend/data/sec/{FILINGS[ticker]['text']}"
        record.update({
            "statement": "10-K narrative",
            "question": spec["question"],
            "line_item": spec["quote"],
            "source_quote": spec["quote"],
            "gold_value": spec["value"],
            "gold_unit": spec["unit"],
            "allow_scale_conversion": True,
        })
        questions.append(record)

    seen_questions = set()
    unique_questions = []
    for record in questions:
        key = _normalize_question(record["question"])
        if key in seen_questions or key in existing:
            continue
        seen_questions.add(key)
        unique_questions.append(record)
    questions = unique_questions[:150]
    if len(questions) < 150:
        limitation = (
            f"The on-disk filings support {len(questions)} verified questions "
            "that are distinct from the existing sets. No further questions "
            "were added."
        )
    for index, record in enumerate(questions, start=1):
        record["id"] = f"dev-{index:03d}"
    return questions, limitation


def verify_questions(questions: Sequence[Dict[str, Any]]) -> List[str]:
    """Return reasons a stored question is not grounded in its source file."""

    parsed_cache: Dict[str, str] = {}
    reasons = []
    for question in questions:
        source = PROJECT_ROOT / str(question.get("source_file", ""))
        if not source.exists():
            reasons.append(f"{question.get('id')}: missing {source.name}")
            continue
        document = _collapse(source.read_text(encoding="utf-8", errors="replace"))
        quote = question.get("source_quote")
        if not quote or _collapse(quote) not in document:
            reasons.append(f"{question.get('id')}: source quote is not in the filing")
        if question.get("gold_value") is None and question.get("expected_answer") != "abstain":
            reasons.append(f"{question.get('id')}: gold value is empty")
        for field in ("source_line", "source_line_extra"):
            line = question.get(field)
            if not line:
                continue
            if source.suffix.lower() != ".html":
                reasons.append(f"{question.get('id')}: table line points at a non-HTML filing")
                continue
            if source.name not in parsed_cache:
                chunks = extract_table_chunks(
                    str(source),
                    metadata={"form": "10-K", "filing": source.name},
                )
                parsed_cache[source.name] = "\n".join(chunk.get("text", "") for chunk in chunks)
            if line not in parsed_cache[source.name]:
                reasons.append(f"{question.get('id')}: table line is not in the parsed filing")
    return reasons


def main() -> int:
    questions, limitation = build_questions()
    reasons = verify_questions(questions)
    if reasons:
        print(f"verification failed for {len(reasons)} question(s). File not written.")
        for reason in reasons[:20]:
            print(reason)
        return 2
    QUESTIONS_PATH.write_text(json.dumps(questions, indent=2), encoding="utf-8")
    counts: Dict[str, int] = {}
    for question in questions:
        counts[question["category"]] = counts.get(question["category"], 0) + 1
    print(f"wrote {len(questions)} questions to {QUESTIONS_PATH.name}")
    print("categories", counts)
    if limitation:
        print(limitation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
