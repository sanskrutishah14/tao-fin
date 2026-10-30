"""Build a 150-question holdout from SEC 10-Ks that are not in the development sets.

Gold comes from those filings. This does not change the answering
pipeline or the scorer, and it does not rewrite the development sets.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
SOURCES = PROJECT_ROOT / "evaluation" / "holdout_sources"
QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "holdout_150_questions.json"
NOTES_PATH = PROJECT_ROOT / "evaluation" / "holdout_150_notes.json"
CACHE_PATH = SOURCES / "parsed_rows_cache.json"

for _path in (PROJECT_ROOT, BACKEND_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from app.services.calculator import CalculatorError, growth_rate  # noqa: E402
from app.services.financial_lookup import _is_weak_label, _normalize_question  # noqa: E402
from app.services.table_parser import extract_table_chunks  # noqa: E402
from evaluation.validation_150 import (  # noqa: E402
    _acceptable_label,
    _lookup_question,
    _longest_match,
    _quote_for,
    canonical_label,
)
from app.services.financial_lookup import _extract_year_values  # noqa: E402

INDEX_NAMES = {
    "JNJ": "Johnson & Johnson",
    "KO": "Coca-Cola Company",
    "CAT": "Caterpillar Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "XOM": "Exxon Mobil Corporation",
    "WMT": "Walmart Inc.",
    "NEE": "NextEra Energy, Inc.",
    "PFE": "Pfizer Inc.",
}
SECTORS = {
    "JNJ": "health care",
    "KO": "consumer staples",
    "CAT": "industrials",
    "JPM": "financials",
    "XOM": "energy",
    "WMT": "consumer retail",
    "NEE": "utilities",
    "PFE": "health care",
}
GENERIC = {"all other", "other", "total", "net", "subtotal", "miscellaneous", "various"}
SKIP_PHRASES = (
    "employee",
    "headcount",
    "full time",
    "square foot",
    "percentage of",
    "per share",
    "footnote",
)
MONEY_RE = re.compile(
    r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(billion|million|thousand)s?\b",
    re.I,
)
NUMERATORS = {
    "gross margin": ("gross profit",),
    "operating margin": ("operating income", "operating profit"),
    "net margin": ("net income", "net earnings"),
}
DENOMINATORS = (
    "net sales",
    "total net sales",
    "total revenues",
    "total revenue",
    "total net revenue",
    "net revenues",
    "revenues",
    "revenue",
)


def _load_manifest() -> List[Dict[str, Any]]:
    return json.loads((SOURCES / "manifest.json").read_text(encoding="utf-8"))


def _existing_questions() -> Tuple[set, set]:
    names = (
        "smoke_questions.json",
        "validation_questions.json",
        "validation_50_questions.json",
        "validation_150_questions.json",
    )
    text = set()
    years = set()
    for name in names:
        payload = json.loads((PROJECT_ROOT / "evaluation" / name).read_text(encoding="utf-8"))
        for item in payload:
            if item.get("question"):
                text.add(_normalize_question(item["question"]))
            if item.get("fiscal_year"):
                years.add(int(item["fiscal_year"]))
    return text, years


def _year_once(line: str, year: int) -> bool:
    return line.count(f"{year}=") == 1


def _usable_label(canonical: str) -> bool:
    if not _acceptable_label(canonical) or _is_weak_label(canonical):
        return False
    if canonical in GENERIC or re.search(r"\d", canonical):
        return False
    if "shares outstanding" in canonical or canonical.startswith("average shares"):
        return False
    return True


def _as_billions(value: float, scale: str) -> Optional[float]:
    if scale == "billion":
        return float(value)
    if scale == "million":
        return float(value) / 1000.0
    if scale == "thousand":
        return float(value) / 1_000_000.0
    return None


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _quote_collapsed(collapsed: str, value: float) -> Optional[str]:
    """Find a number in text that is already single-spaced."""

    if value <= 0:
        return None
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
        if candidate and re.search(rf"(?<![\d,.]){re.escape(candidate)}(?![\d,.])", collapsed):
            return candidate
    return None


def _signed_quote(collapsed: str, value: float) -> Optional[str]:
    if value > 0:
        return _quote_collapsed(collapsed, value)
    magnitude = abs(float(value))
    if float(magnitude) == int(magnitude):
        text = f"{int(magnitude):,}"
    else:
        rendered = f"{magnitude:.6f}".rstrip("0").rstrip(".")
        whole, frac = rendered.split(".", 1)
        text = f"{int(whole):,}.{frac}"
    if re.search(rf"\(\s*{re.escape(text)}\s*\)", collapsed):
        return f"({text})"
    return None


def _rows_from_chunks(chunks: List[Dict]) -> List[Dict[str, Any]]:
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
            rows.append({
                "canonical": canonical_label(label),
                "scale": scale,
                "values": {str(year): value for year, value in values.items()},
                "line": line.strip(),
            })
    return rows


def _load_cache() -> Dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def _save_cache(cache: Dict[str, Any]) -> None:
    CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def _parsed_rows(meta: Dict[str, Any], cache: Dict[str, Any]) -> List[Dict[str, Any]]:
    html_path = SOURCES / meta["html"]
    key = meta["html"]
    mtime = html_path.stat().st_mtime
    cached = cache.get(key)
    if cached and cached.get("mtime") == mtime:
        print(f"cache {key} rows {len(cached['rows'])}", flush=True)
        return cached["rows"]
    print(f"parsing {key}", flush=True)
    chunks = extract_table_chunks(
        str(html_path),
        metadata={
            "company": meta["ticker"],
            "form": "10-K",
            "filing": meta["html"],
            "source": "SEC EDGAR",
        },
    )
    rows = _rows_from_chunks(chunks)
    cache[key] = {"mtime": mtime, "rows": rows}
    _save_cache(cache)
    print(f"parsed {key} rows {len(rows)}", flush=True)
    return rows


def _int_values(row: Dict[str, Any]) -> Dict[int, float]:
    return {int(year): float(value) for year, value in row["values"].items()}


def _fresh(question: str, existing: set) -> bool:
    return _normalize_question(question) not in existing


def _best_label(question: str, labels: set) -> Optional[str]:
    """Longest statement label that appears in the question, or blank on a tie."""

    words = _normalize_question(question).split()
    found = []
    for length in range(1, len(words) + 1):
        for start in range(0, len(words) - length + 1):
            phrase = " ".join(words[start:start + length])
            if phrase in labels:
                found.append(phrase)
    if not found:
        return None
    found.sort(key=len, reverse=True)
    if len(found) > 1 and len(found[0]) == len(found[1]):
        return ""
    return found[0]


def _round_robin(pool: List[Dict], count: int, order: Sequence[str]) -> List[Dict]:
    buckets: Dict[str, List[Dict]] = {ticker: [] for ticker in order}
    seen = set()
    for item in sorted(pool, key=lambda row: (row["canonical"], -int(row["year"]))):
        key = (item["ticker"], item["canonical"], item.get("kind", "level"), item["year"])
        if key in seen:
            continue
        seen.add(key)
        buckets.setdefault(item["ticker"], []).append(item)
    picked = []
    while len(picked) < count and any(buckets.values()):
        for ticker in order:
            if not buckets.get(ticker):
                continue
            picked.append(buckets[ticker].pop(0))
            if len(picked) >= count:
                break
    return picked


def _record(meta: Dict[str, Any], year: int, category: str, dev_years: set) -> Dict[str, Any]:
    ticker = meta["ticker"]
    period = "unseen_period" if int(year) not in dev_years else "seen_period_new_company"
    return {
        "ticker": ticker,
        "cik": meta["cik"],
        "company": meta["company"],
        "ask": meta["ask"],
        "index_name": INDEX_NAMES[ticker],
        "sector": SECTORS[ticker],
        "form": "10-K",
        "fiscal_year": int(year),
        "accession": meta["accession"],
        "report_date": meta["report_date"],
        "filing_date": meta["filing_date"],
        "source_url": meta["source_url"],
        "source_file": f"evaluation/holdout_sources/{meta['html']}",
        "category": category,
        "holdout_group": "unseen_company",
        "period_group": period,
        "expected_path": "not used for scoring",
        "answer_mode": "numeric",
        "tolerance_mode": "exact",
        "tolerance_abs": 0,
    }


def _collapsed_filing(meta: Dict[str, Any], cache: Dict[str, str]) -> str:
    name = meta["html"]
    if name not in cache:
        cache[name] = _collapse((SOURCES / name).read_text(encoding="utf-8", errors="replace"))
    return cache[name]


def _facts(filings: List[Dict[str, Any]], dev_years: set) -> Tuple[List[Dict], List[str], Dict[str, int]]:
    cache = _load_cache()
    prepared = []
    canonicals = set()
    coverage: Dict[str, int] = {}
    for meta in filings:
        rows = _parsed_rows(meta, cache)
        latest = int(str(meta["report_date"])[:4])
        usable = 0
        for row in rows:
            canonicals.add(row["canonical"])
            if row.get("scale") in {"million", "billion", "thousand"} and _usable_label(row["canonical"]):
                usable += 1
            prepared.append((meta, latest, row))
        coverage[meta["ticker"]] = coverage.get(meta["ticker"], 0) + usable
    print(f"matching {len(prepared)} parsed rows", flush=True)
    labels = set(canonicals)
    found = []
    for meta, latest, row in prepared:
        if not _usable_label(row["canonical"]) or row.get("scale") not in {"million", "billion", "thousand"}:
            continue
        values = _int_values(row)
        for year, value in values.items():
            if year < latest - 4 or year > latest or value == 0:
                continue
            if not _year_once(row["line"], year):
                continue
            if abs(value) < 0.05:
                continue
            question = _lookup_question(meta["ask"], row["canonical"], year, row["scale"])
            if _best_label(question, labels) != row["canonical"]:
                continue
            found.append({
                "ticker": meta["ticker"],
                "meta": meta,
                "year": year,
                "canonical": row["canonical"],
                "value": value,
                "scale": row["scale"],
                "line": row["line"],
                "question": question,
                "latest": latest,
                "kind": "level",
                "unseen": year not in dev_years,
            })
    print(f"candidate facts {len(found)}", flush=True)
    return found, labels, coverage


def _unique_level(rows: List[Dict], canonical: str, year: int) -> Optional[Dict]:
    chosen = []
    for row in rows:
        values = _int_values(row)
        if row["canonical"] != canonical or year not in values:
            continue
        if row.get("scale") not in {"million", "billion", "thousand"}:
            continue
        if not _year_once(row["line"], year):
            continue
        chosen.append((values[year], row))
    signatures = {(round(value, 6), row["scale"]) for value, row in chosen}
    if len(signatures) != 1:
        return None
    value, row = chosen[0]
    return {"value": value, "scale": row["scale"], "line": row["line"]}


def _ratios(filings, cache_rows, collapsed, canonicals, existing) -> List[Dict]:
    kept = []
    for meta in filings:
        if meta.get("cohort") == "fy2021":
            continue
        rows = cache_rows[meta["html"]]
        year = int(str(meta["report_date"])[:4])
        denom = None
        for canonical in DENOMINATORS:
            found = _unique_level(rows, canonical, year)
            if not found or found["value"] <= 0:
                continue
            billions = _as_billions(found["value"], found["scale"])
            if billions is None or billions < 15:
                continue
            if denom is None or billions > denom["billions"]:
                denom = {**found, "canonical": canonical, "billions": billions}
        if denom is None:
            continue
        for metric, names in NUMERATORS.items():
            numerator = None
            for name in names:
                found = _unique_level(rows, name, year)
                if found and found["scale"] == denom["scale"] and found["value"] > 0:
                    numerator = {**found, "canonical": name}
                    break
            if numerator is None or numerator["value"] >= denom["value"]:
                continue
            percent = round(numerator["value"] / denom["value"] * 100, 2)
            if not 20 < percent < 80:
                continue
            question = f"What was {meta['ask']}'s {metric} for fiscal year {year}?"
            if not _fresh(question, existing):
                continue
            document = _collapsed_filing(meta, collapsed)
            quote = _signed_quote(document, numerator["value"])
            if quote is None:
                continue
            kept.append({
                "meta": meta,
                "ticker": meta["ticker"],
                "year": year,
                "canonical": metric,
                "question": question,
                "gold": percent,
                "numerator": numerator["value"],
                "denominator": denom["value"],
                "numerator_line": numerator["line"],
                "denominator_line": denom["line"],
                "quote": quote,
                "kind": metric,
            })
            break
    return kept


def _pairs(filings, cache_rows, collapsed, canonicals) -> List[Dict]:
    pairs = []
    for meta in filings:
        rows = cache_rows[meta["html"]]
        grouped: Dict[str, List[Dict]] = {}
        for row in rows:
            if not _usable_label(row["canonical"]) or row.get("scale") not in {"million", "thousand"}:
                continue
            if re.search(r"\b(?:change|difference)\b", row["canonical"]):
                continue
            grouped.setdefault(row["canonical"], []).append(row)
        for canonical, group in grouped.items():
            usable = []
            for row in group:
                values = _int_values(row)
                years = sorted(
                    year for year, value in values.items()
                    if value > 0 and _year_once(row["line"], year)
                )
                if len(years) < 2:
                    continue
                earlier, later = years[-2], years[-1]
                if values[earlier] == 0:
                    continue
                usable.append((row, earlier, later, values))
            if not usable:
                continue
            signatures = {
                (
                    round(values[earlier], 6),
                    round(values[later], 6),
                    row["scale"],
                )
                for row, earlier, later, values in usable
            }
            if len(signatures) != 1:
                continue
            row, earlier, later, values = usable[0]
            document = _collapsed_filing(meta, collapsed)
            quote = _signed_quote(document, values[later])
            if quote is None:
                continue
            try:
                percent = round(growth_rate(values[earlier], values[later]), 2)
            except CalculatorError:
                continue
            growth_question = (
                f"What was the growth rate in {meta['ask']}'s {canonical} "
                f"from fiscal year {earlier} to fiscal year {later}, in percent?"
            )
            if row["scale"] == "million":
                change_question = (
                    f"By how many USD millions did {meta['ask']}'s {canonical} "
                    f"change from fiscal year {earlier} to fiscal year {later}?"
                )
            else:
                change_question = (
                    f"By how many USD thousands did {meta['ask']}'s {canonical} "
                    f"change from fiscal year {earlier} to fiscal year {later}?"
                )
            if _best_label(growth_question, set(canonicals) if not isinstance(canonicals, set) else canonicals) != canonical:
                continue
            pairs.append({
                "ticker": meta["ticker"],
                "meta": meta,
                "canonical": canonical,
                "year": later,
                "earlier": earlier,
                "later": later,
                "scale": row["scale"],
                "start": values[earlier],
                "end": values[later],
                "line": row["line"],
                "quote": quote,
                "percent": percent,
                "delta": round(values[later] - values[earlier], 6),
                "growth_question": growth_question,
                "change_question": change_question,
                "kind": "pair",
            })
    return pairs


def _narratives(filings, existing) -> List[Dict]:
    rules = (
        ("dividends paid totaled", "dividends paid"),
        ("repurchased", "common stock repurchased"),
        ("authorized a new", "newly authorized common share repurchase program"),
    )
    kept = []
    seen = set()
    for meta in filings:
        if meta.get("cohort") == "fy2021":
            continue
        collapsed = _collapse((SOURCES / meta["text"]).read_text(encoding="utf-8", errors="replace"))
        for sentence in re.split(r"(?<=[.!?])\s+", collapsed):
            amounts = list(MONEY_RE.finditer(sentence))
            if len(amounts) != 1:
                continue
            lowered = sentence.lower()
            label = next((name for needle, name in rules if needle in lowered), None)
            if label is None:
                continue
            amount = amounts[0]
            raw = amount.group(1)
            decimals = len(raw.split(".", 1)[1]) if "." in raw else 0
            value = round(float(raw.replace(",", "")), decimals)
            unit = amount.group(2).lower().rstrip("s")
            question = (
                f"How many USD {unit}s did the {meta['ask']} filing state for "
                f"{label}?"
            )
            if question in seen or not _fresh(question, existing):
                continue
            seen.add(question)
            kept.append({
                "meta": meta,
                "ticker": meta["ticker"],
                "year": int(str(meta["report_date"])[:4]),
                "question": question,
                "quote": sentence.strip()[:500],
                "value": value,
                "unit": unit,
                "label": label,
            })
            break
    return kept


def _with_quote(item: Dict, collapsed: Dict[str, str]) -> Optional[Dict]:
    if item.get("quote"):
        return item
    document = _collapsed_filing(item["meta"], collapsed)
    quote = _signed_quote(document, item["value"])
    if quote is None:
        return None
    return {**item, "quote": quote}


def _lookup_record(item: Dict, category: str, dev_years: set, existing: set) -> Optional[Dict]:
    if not item.get("quote") or not _fresh(item["question"], existing):
        return None
    record = _record(item["meta"], item["year"], category, dev_years)
    record.update({
        "statement": "10-K table",
        "question": item["question"],
        "line_item": item["canonical"],
        "source_quote": item["quote"],
        "source_line": item["line"],
        "gold_value": item["value"] if category == "lookup" else item.get("converted", item["value"]),
        "gold_unit": item["scale"] if category == "lookup" else item.get("gold_unit", item["scale"]),
        "allow_scale_conversion": True,
    })
    return record


def _arrange(questions: List[Dict]) -> List[Dict]:
    """Put one of each category, including an unseen period, at the front for the pilot."""

    wanted = [
        ("lookup", "unseen_period"),
        ("lookup", "seen_period_new_company"),
        ("unit_conversion", None),
        ("ratio", None),
        ("growth", None),
        ("comparison", None),
        ("narrative", None),
        ("insufficient_evidence", None),
    ]
    front = []
    used = set()
    for category, period in wanted:
        for index, question in enumerate(questions):
            if index in used or question["category"] != category:
                continue
            if period and question["period_group"] != period:
                continue
            front.append(question)
            used.add(index)
            break
    rest = [question for index, question in enumerate(questions) if index not in used]
    ordered = front + rest
    for number, question in enumerate(ordered, start=1):
        question["id"] = f"hold-{number:03d}"
    return ordered


def build_questions() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    manifest = _load_manifest()
    filings = [row for row in manifest if row["ticker"] in INDEX_NAMES]
    order = [ticker for ticker in INDEX_NAMES if any(row["ticker"] == ticker for row in filings)]
    existing, dev_years = _existing_questions()
    facts, canonicals, coverage = _facts(filings, dev_years)
    cache = _load_cache()
    cache_rows = {meta["html"]: cache[meta["html"]]["rows"] for meta in filings if meta["html"] in cache}
    collapsed: Dict[str, str] = {}
    questions: List[Dict[str, Any]] = []
    used = set()

    def take(pool: List[Dict], count: int, category: str) -> None:
        accepted = 0
        for item in _round_robin(pool, max(count * 4, count), order):
            if accepted >= count:
                break
            quoted = _with_quote(item, collapsed)
            if quoted is None:
                continue
            record = _lookup_record(quoted, category, dev_years, existing)
            if record is None:
                continue
            if category == "unit_conversion":
                record["gold_value"] = item["converted"]
                record["gold_unit"] = "billion"
                record["inputs"] = {
                    "source_value": item["value"],
                    "source_unit": "million",
                    "formula": f"{item['value']} million = {item['converted']} billion",
                }
            questions.append(record)
            used.add((item["ticker"], item["canonical"], item["year"], item["meta"]["accession"]))
            existing.add(_normalize_question(item["question"]))
            accepted += 1

    unseen = [item for item in facts if item["unseen"] and item["value"] > 0]
    latest = [
        item for item in facts
        if item["year"] == item["latest"] and item["value"] > 0
        and (item["ticker"], item["canonical"], item["year"], item["meta"]["accession"]) not in {
            (row["ticker"], row["canonical"], row["year"], row["meta"]["accession"]) for row in unseen
        }
    ]
    take(unseen, 36, "lookup")
    take(latest, 52, "lookup")

    conversions = []
    for item in facts:
        key = (item["ticker"], item["canonical"], item["year"], item["meta"]["accession"])
        if key in used or item["scale"] != "million" or item["value"] < 1000:
            continue
        converted = round(item["value"] / 1000.0, 6)
        question = _lookup_question(item["meta"]["ask"], item["canonical"], item["year"], "billion")
        if not _fresh(question, existing) or _best_label(question, set(canonicals)) != item["canonical"]:
            continue
        conversions.append({**item, "question": question, "converted": converted, "kind": "conversion"})
    take(conversions, 14, "unit_conversion")

    for item in _ratios(filings, cache_rows, collapsed, canonicals, existing)[:8]:
        record = _record(item["meta"], item["year"], "ratio", dev_years)
        record.update({
            "statement": "10-K table",
            "question": item["question"],
            "line_item": item["canonical"],
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
                "formula": f"round({item['numerator']} / {item['denominator']} * 100, 2)",
            },
        })
        questions.append(record)
        existing.add(_normalize_question(item["question"]))

    pairs = _pairs(filings, cache_rows, collapsed, canonicals)
    growth_items = _round_robin(pairs, 12, order)
    growth_keys = {(item["ticker"], item["canonical"], item["meta"]["accession"]) for item in growth_items}
    change_items = _round_robin(
        [item for item in pairs if (item["ticker"], item["canonical"], item["meta"]["accession"]) not in growth_keys],
        10,
        order,
    )
    for item in growth_items:
        if not _fresh(item["growth_question"], existing):
            continue
        record = _record(item["meta"], item["later"], "growth", dev_years)
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
                "formula": f"round(({item['end']} - {item['start']}) / {item['start']} * 100, 2)",
            },
        })
        questions.append(record)
        existing.add(_normalize_question(item["growth_question"]))
    for item in change_items:
        if not _fresh(item["change_question"], existing):
            continue
        record = _record(item["meta"], item["later"], "comparison", dev_years)
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
        existing.add(_normalize_question(item["change_question"]))

    for item in _narratives(filings, existing)[:8]:
        record = _record(item["meta"], item["year"], "narrative", dev_years)
        record.update({
            "statement": "10-K narrative",
            "question": item["question"],
            "line_item": item["label"],
            "source_quote": item["quote"],
            "gold_value": item["value"],
            "gold_unit": item["unit"],
            "allow_scale_conversion": True,
            "source_file": f"evaluation/holdout_sources/{item['meta']['text']}",
        })
        questions.append(record)
        existing.add(_normalize_question(item["question"]))

    abstain_tickers = set()
    for item in facts:
        if item["ticker"] in abstain_tickers or item["value"] <= 0 or item["year"] != item["latest"]:
            continue
        if item["scale"] != "million":
            continue
        question = (
            f"What was {item['meta']['ask']}'s {item['canonical']} for fiscal year "
            f"{item['year']}, in euros?"
        )
        if not _fresh(question, existing) or _best_label(question, set(canonicals)) != item["canonical"]:
            continue
        quoted = _with_quote(item, collapsed)
        if quoted is None:
            continue
        record = _record(quoted["meta"], quoted["year"], "insufficient_evidence", dev_years)
        record.update({
            "statement": "10-K table states a dollar scale, not euros",
            "question": question,
            "line_item": quoted["canonical"],
            "source_quote": quoted["quote"],
            "source_line": item["line"],
            "gold_value": None,
            "gold_text": "Insufficient evidence.",
            "gold_unit": None,
            "allow_scale_conversion": False,
            "expected_answer": "abstain",
            "evidence_note": (
                "The filing states this line in the table's dollar scale. "
                "No euro amount or exchange rate is in the filing."
            ),
        })
        questions.append(record)
        existing.add(_normalize_question(question))
        abstain_tickers.add(item["ticker"])

    negatives = [
        item for item in facts
        if item["value"] < 0
        and (item["ticker"], item["canonical"], item["year"], item["meta"]["accession"]) not in used
        and _fresh(item["question"], existing)
    ]
    for item in _round_robin(negatives, 24, order):
        if sum(1 for row in questions if row.get("gold_value") is not None and row["gold_value"] < 0) >= 8:
            break
        quoted = _with_quote(item, collapsed)
        if quoted is None:
            continue
        record = _lookup_record(quoted, "lookup", dev_years, existing)
        if record is None:
            continue
        questions.append(record)
        used.add((item["ticker"], item["canonical"], item["year"], item["meta"]["accession"]))
        existing.add(_normalize_question(item["question"]))

    if len(questions) < 150:
        extras = [
            item for item in facts
            if item["value"] > 0
            and (item["ticker"], item["canonical"], item["year"], item["meta"]["accession"]) not in used
            and _fresh(item["question"], existing)
        ]
        for item in _round_robin(extras, max(150 - len(questions), 1) * 3, order):
            if len(questions) >= 150:
                break
            quoted = _with_quote(item, collapsed)
            if quoted is None:
                continue
            record = _lookup_record(quoted, "lookup", dev_years, existing)
            if record is None:
                continue
            questions.append(record)
            used.add((item["ticker"], item["canonical"], item["year"], item["meta"]["accession"]))
            existing.add(_normalize_question(item["question"]))
            if len(questions) >= 150:
                break

    questions = _arrange(questions[:150])
    companies = {}
    for meta in filings:
        companies.setdefault(meta["ticker"], {
            "company": meta["company"],
            "sector": SECTORS[meta["ticker"]],
            "filings": [],
        })
        companies[meta["ticker"]]["filings"].append({
            "report_date": meta["report_date"],
            "accession": meta["accession"],
            "source_url": meta["source_url"],
            "cohort": meta.get("cohort", "latest"),
        })
    notes = {
        "label": (
            "Independent holdout. Companies are absent from the smoke, validation, "
            "50-question, and 150-question development sets. Not a guarantee of "
            "overall financial accuracy."
        ),
        "companies": companies,
        "scaled_row_counts": coverage,
        "development_fiscal_years": sorted(dev_years),
        "question_count": len(questions),
        "unseen_company_count": sum(1 for item in questions if item["holdout_group"] == "unseen_company"),
        "unseen_period_count": sum(1 for item in questions if item["period_group"] == "unseen_period"),
        "seen_period_new_company_count": sum(
            1 for item in questions if item["period_group"] == "seen_period_new_company"
        ),
        "categories": {},
        "limitations": [
            "Every issuer is absent from the retained smoke, validation, 50-question, and 150-question files. The deleted FinanceBench diagnostic did not leave a company list in the working tree.",
            "Latest 10-K comparative columns use 2023, 2024, 2025, or 2026. Those year numbers already appear in the development sets, so those questions are seen_period_new_company even though the company is new.",
            "unseen_period questions use a fiscal year that is not a requested year in the development files. They come from FY2021 10-Ks when that filing was available.",
            "A table line is used only when the requested fiscal year appears once on that line. Lines that repeat a year, including pension rollforwards concatenated by the parser, are excluded.",
            "Ratios use one unique profit line and the largest unique revenue or net-sales line in the same scale. The margin must be above 20 and below 80 percent, and the revenue total must be at least 15 billion dollars. A profit line that is too small to be the consolidated total is omitted.",
            "Narrative gold is the single dollar amount in the cited sentence. These questions were not chosen because the current narrative reader already answers them.",
            "Insufficient-evidence items ask for euros. The cited line is stated in the table's dollar scale and the filing provides no exchange rate. An abstention is the expected result and is not added to the correct count.",
            "Exxon tables that say only '(millions of dollars)' do not receive a parser scale. Those rows are not used as gold.",
            "No live market price is used as gold.",
        ],
    }
    for question in questions:
        notes["categories"][question["category"]] = notes["categories"].get(question["category"], 0) + 1
    return questions, notes


def verify_questions(questions: Sequence[Dict[str, Any]]) -> List[str]:
    cache = _load_cache()
    documents: Dict[str, str] = {}
    reasons = []
    seen = set()
    for question in questions:
        if question["question"] in seen:
            reasons.append(f"{question['id']}: duplicate question text")
        seen.add(question["question"])
        source = PROJECT_ROOT / str(question.get("source_file", ""))
        if not source.exists():
            reasons.append(f"{question.get('id')}: missing {source.name}")
            continue
        if source.name not in documents:
            documents[source.name] = _collapse(source.read_text(encoding="utf-8", errors="replace"))
        quote = _collapse(str(question.get("source_quote") or ""))
        if not quote or quote not in documents[source.name]:
            reasons.append(f"{question.get('id')}: source quote is not in the filing")
        if question.get("gold_value") is None and question.get("expected_answer") != "abstain":
            reasons.append(f"{question.get('id')}: gold value is empty")
        for field in ("source_line", "source_line_extra"):
            line = question.get(field)
            if not line:
                continue
            year = int(question["fiscal_year"])
            if field == "source_line" and line.count(f"{year}=") != 1 and question["category"] != "growth":
                if question["category"] != "comparison":
                    reasons.append(f"{question.get('id')}: {field} repeats {year}")
            html_name = source.name if source.suffix.lower() == ".html" else None
            if html_name is None:
                reasons.append(f"{question.get('id')}: table line points at a non-HTML filing")
                continue
            cached = cache.get(html_name) or {}
            blob = "\n".join(row.get("line", "") for row in cached.get("rows") or [])
            if line not in blob:
                reasons.append(f"{question.get('id')}: table line is not in the parsed filing")
        if question["category"] in {"growth", "comparison"}:
            line = question.get("source_line") or ""
            for key in ("start_year", "end_year", "earlier_year", "later_year"):
                year = (question.get("inputs") or {}).get(key)
                if year is not None and line.count(f"{int(year)}=") != 1:
                    reasons.append(f"{question.get('id')}: {key} {year} is not unique on the line")
    return reasons


def main() -> int:
    if QUESTIONS_PATH.exists():
        print(f"refusing to overwrite {QUESTIONS_PATH.name}")
        return 2
    questions, notes = build_questions()
    reasons = verify_questions(questions)
    if reasons:
        print(f"verification failed for {len(reasons)} question(s). File not written.")
        for reason in reasons[:40]:
            print(reason)
        return 2
    if len(questions) < 150:
        print(f"verified only {len(questions)} questions. File written with that count.")
    QUESTIONS_PATH.write_text(json.dumps(questions, indent=2), encoding="utf-8")
    NOTES_PATH.write_text(json.dumps(notes, indent=2), encoding="utf-8")
    print(f"wrote {len(questions)} questions")
    print("categories", notes["categories"])
    print(
        "unseen_company", notes["unseen_company_count"],
        "unseen_period", notes["unseen_period_count"],
        "seen_period_new_company", notes["seen_period_new_company_count"],
    )
    print("scaled_rows", notes["scaled_row_counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
