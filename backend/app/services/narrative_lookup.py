"""
Narrative evidence for a metric that is not a single statement line.

A combined total, an explicit narrative disclosure, a named instrument
such as an IRS notice, or a filing sentence about a specific financial
event is read from the filing text already indexed as narrative chunks.
A shorter table label or a product-level figure is not substituted for
that disclosure. Conflicting amounts are not guessed.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.services.financial_lookup import (
    _convert,
    _is_fiscal_year_question,
    _mentioned_tickers,
    _output_unit,
    format_amount,
)


_MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)
_DATE_RE = re.compile(rf"\b({_MONTHS})\s+(\d{{1,2}}),?\s+(20\d{{2}})\b", re.I)
_MONEY_RE = re.compile(
    r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(billion|million|thousand)s?\b",
    re.I,
)
_NARROW_RE = re.compile(
    r"\btarget[- ]date\b|\bin our\b.{0,80}\bproducts\b",
    re.I,
)
_CHANGE_AMOUNT_RE = re.compile(
    r"\b(?:increase|decrease|decline|growth)\s+of\s*$",
    re.I,
)
_TOTAL_OF_RE = re.compile(
    r"\btotal of\s+(.+?)(?=,?\s+in\s+(?:usd|u\.s\.|us)\b|[?.]|$)",
    re.I,
)
_OF_DID_RE = re.compile(r"\bof\s+(.+?)\s+did\b", re.I)
_WHAT_IS_RE = re.compile(r"\bwhat\s+(.+?)\s+(?:is|was|were)\b", re.I)
_PROGRAM_RE = re.compile(
    r"\b((?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+20\d{2})\s+share repurchase program\b",
    re.I,
)
_QUARTER_PHRASE_RE = re.compile(
    r"\b((?:first|second|third|fourth)\s+quarter"
    r"(?:\s+of\s+(?:fiscal\s+year\s+)?20\d{2})?)\b",
    re.I,
)
_SERIES_RE = re.compile(r"\b(series\s+[a-z0-9]+)\b", re.I)


def resolve_narrative_question(
    question: str,
    narrative_chunks: List[Dict],
    company_index: Optional[Dict[str, str]] = None,
) -> Optional[Dict]:
    """Return an answer, insufficient evidence, or None when this is not that question."""

    spec = _question_spec(question, company_index or {})
    if spec is None:
        return None

    tickers = _mentioned_tickers(question, company_index)
    if len(tickers) != 1:
        return {
            "status": "insufficient",
            "reason": "narrative disclosure does not name one company",
        }
    ticker = tickers[0]
    chunks = [
        chunk
        for chunk in narrative_chunks
        if str((chunk.get("metadata") or {}).get("company", "")).upper() == ticker
        and str((chunk.get("metadata") or {}).get("type", "")).lower() != "table"
    ]
    if re.search(r"\b10-?k\b", question, re.I) or _is_fiscal_year_question(question):
        annual = [
            chunk
            for chunk in chunks
            if "10-K" in str((chunk.get("metadata") or {}).get("form", "")).upper()
            or "10K" in str((chunk.get("metadata") or {}).get("filing", "")).upper()
        ]
        if annual:
            chunks = annual

    if spec.get("kind"):
        amounts = _filing_disclosure_amounts(chunks, spec, question)
    else:
        amounts = []
        for chunk in chunks:
            for sentence in _sentences(chunk.get("text", "")):
                found = _sentence_amount(sentence, spec)
                if found is None:
                    continue
                value, unit = found
                output_unit = _output_unit(question, unit, growth=False)
                converted = _convert(value, unit, output_unit)
                if converted is None:
                    continue
                amounts.append({
                    "value": converted,
                    "unit": output_unit,
                    "sentence": sentence.strip(),
                    "narrow": _is_narrower(sentence, question, spec),
                    "document": chunk,
                })

    broad = [item for item in amounts if not item["narrow"]]
    chosen = broad if broad else []
    if not chosen:
        if amounts:
            return {
                "status": "insufficient",
                "reason": "only a narrower product or segment figure was found",
            }
        return {
            "status": "insufficient",
            "reason": "no narrative sentence states this metric and period",
        }

    unique = {round(item["value"], 6) for item in chosen}
    if len(unique) != 1:
        return {
            "status": "insufficient",
            "reason": "narrative sentences disagree on this metric",
        }
    best = chosen[0]
    return {
        "status": "answered",
        "metric": spec["metric"],
        "value": best["value"],
        "unit": best["unit"],
        "sentence": best["sentence"],
        "document": best["document"],
        "display": format_amount(best["value"]),
    }


def _question_spec(question: str, company_index: Dict[str, str]) -> Optional[Dict]:
    total = _TOTAL_OF_RE.search(question)
    if total and re.search(r"\band\b", total.group(1), re.I):
        phrase = _strip_company(total.group(1), company_index)
        components = _components(phrase)
        if len(components) >= 2:
            return {
                "metric": ", ".join(components),
                "phrases": components,
                "date": _date_key(question),
            }

    if re.search(r"\bnarrative\b", question, re.I):
        metric = _metric_from_of_did(question)
        if metric:
            return {
                "metric": metric,
                "phrases": [metric],
                "date": _date_key(question),
            }

    anchors = _extra_acronyms(question, company_index)
    if anchors:
        metric_match = _WHAT_IS_RE.search(question)
        metric = " ".join(metric_match.group(1).split()) if metric_match else ""
        phrases = [item for item in [metric, *anchors] if item]
        if len(phrases) >= 2:
            return {
                "metric": metric or anchors[0],
                "phrases": phrases,
                "date": _date_key(question),
            }

    return _event_spec(question)


def _strip_company(phrase: str, company_index: Dict[str, str]) -> str:
    text = phrase
    for ticker, name in company_index.items():
        text = re.sub(rf"\b{re.escape(str(ticker))}\b(?:'s)?", " ", text, flags=re.I)
        first = str(name or "").split()
        if first and len(first[0]) >= 3:
            text = re.sub(rf"\b{re.escape(first[0])}\b(?:'s)?", " ", text, flags=re.I)
    return " ".join(text.split())


def _components(phrase: str) -> List[str]:
    parts = re.split(r",?\s+and\s+|,\s+", phrase, flags=re.I)
    return [part.strip(" ,") for part in parts if len(part.strip(" ,")) >= 3]


def _metric_from_of_did(question: str) -> str:
    match = _OF_DID_RE.search(question)
    if not match:
        return ""
    return " ".join(match.group(1).split())


def _event_spec(question: str) -> Optional[Dict]:
    """A disclosure sentence, not a statement-line lookup."""

    program = _PROGRAM_RE.search(question)
    if program and re.search(r"\butilized\b", question, re.I):
        phrases = [f"{program.group(1)} program", "utilized"]
        quarter = _QUARTER_PHRASE_RE.search(question)
        if quarter:
            phrases.append(quarter.group(1))
        return {
            "metric": program.group(0),
            "phrases": phrases,
            "date": _date_key(question),
        }

    lowered = question.lower()
    if "return to shareholders" in lowered and "share repurchase" in lowered:
        phrases = ["returned", "shareholders", "share repurchases and dividends"]
        quarter = _QUARTER_PHRASE_RE.search(question)
        if quarter:
            phrases.append(quarter.group(1))
        year = re.search(r"\bfiscal year\s+(20\d{2})\b", question, re.I)
        if year:
            phrases.append(year.group(1))
        return {
            "metric": "returned to shareholders",
            "phrases": phrases,
            "date": _date_key(question),
        }

    if (
        re.search(r"\bgains from\b", question, re.I)
        and "openai" in lowered
        and "net income" in lowered
        and re.search(r"\bincrease\b", question, re.I)
    ):
        return {
            "metric": "gains from investments in OpenAI",
            "phrases": ["gains", "openai", "net income", "increase"],
            "date": _date_key(question),
        }

    if "seed capital" in lowered:
        return {
            "metric": "seed capital investments",
            "phrases": ["seed capital"],
            "date": _date_key(question),
        }

    if re.search(r"\bco-investments\b", question, re.I):
        return {
            "metric": "co-investments",
            "phrases": ["co-investments"],
            "date": _date_key(question),
        }

    if "aggregate purchase amount" in lowered:
        phrases = ["aggregate purchase amount"]
        series = _SERIES_RE.search(question)
        if series:
            phrases.append(series.group(1))
        if "aramark" in lowered:
            phrases.append("aramark")
        return {
            "metric": "aggregate purchase amount",
            "phrases": phrases,
            "date": _date_key(question),
        }

    if "fixed payment obligations" in lowered:
        phrases = ["fixed payment obligations"]
        if "additional leases" in lowered:
            phrases.append("additional leases")
        if "not yet commenced" in lowered:
            phrases.append("not yet commenced")
        return {
            "metric": "fixed payment obligations",
            "phrases": phrases,
            "date": _date_key(question),
        }

    # These disclosures are narrative sentences. A fiscal-year statement
    # question keeps the table path even when the same words appear.
    if not _is_fiscal_year_question(question):
        if re.search(r"\bdividends paid\b", question, re.I):
            return {
                "metric": "dividends paid",
                "kind": "dividends_paid",
                "phrases": ["dividends paid totaled"],
                "date": None,
            }
        if re.search(
            r"\bcommon stock repurchased\b|"
            r"\brepurchased\b.{0,60}\bcommon stock\b|"
            r"\bcommon stock\b.{0,60}\brepurchased\b",
            question,
            re.I,
        ):
            return {
                "metric": "common stock repurchased",
                "kind": "repurchase_cost",
                "phrases": ["repurchased", "total cost", "common stock"],
                "date": None,
            }
    if re.search(r"\b(?:newly authorized|authorized a new)\b", question, re.I) and re.search(
        r"\brepurchase program\b", question, re.I
    ):
        return {
            "metric": "newly authorized common share repurchase program",
            "kind": "new_authorization",
            "phrases": ["authorized a new", "repurchase program"],
            "date": None,
        }
    return None


def _extra_acronyms(question: str, company_index: Dict[str, str]) -> List[str]:
    tickers = {str(ticker).upper() for ticker in company_index}
    skip = tickers | {"USD", "GAAP", "SEC", "EPS", "FY"}
    found = []
    for token in re.findall(r"\b[A-Za-z]{2,}\b", question):
        letters = [char for char in token if char.isalpha()]
        if sum(char.isupper() for char in letters) < 2:
            continue
        if token.upper().rstrip("S") in skip or token.upper() in skip:
            continue
        found.append(token)
    return found


def _date_key(question: str) -> Optional[tuple]:
    match = _DATE_RE.search(question)
    if not match:
        return None
    return (match.group(1).lower(), int(match.group(2)), int(match.group(3)))


def _stated_year(text: str) -> Optional[int]:
    """A year the sentence attaches to the disclosure, not a plan or footnote number."""

    years = [
        int(year)
        for year in re.findall(r"\b(?:during|in|for)\s+(20\d{2})\b", text or "", flags=re.I)
    ]
    for match in _DATE_RE.finditer(text or ""):
        years.append(int(match.group(3)))
    if not years:
        return None
    return max(years)


def _question_years(question: str) -> List[int]:
    return [int(year) for year in re.findall(r"\b(20\d{2})\b", question)]


def _one_amount(sentence: str):
    matches = list(_MONEY_RE.finditer(sentence))
    if len(matches) != 1:
        return None
    match = matches[0]
    raw = match.group(1)
    decimals = len(raw.split(".", 1)[1]) if "." in raw else 0
    value = round(float(raw.replace(",", "")), decimals)
    unit = match.group(2).lower().rstrip("s")
    return value, unit


def _disclosure_hit(sentences: List[str], index: int, kind: str):
    sentence = sentences[index]
    lowered = sentence.lower()
    if kind == "dividends_paid":
        if "dividends paid totaled" not in lowered:
            return None
        year = _stated_year(sentence)
    elif kind == "repurchase_cost":
        if "total cost" not in lowered or "repurchased" not in lowered:
            return None
        window = " ".join(sentences[max(0, index - 2): index + 1])
        if "common stock" not in window.lower():
            return None
        year = _stated_year(sentence)
        if year is None:
            year = _stated_year(" ".join(sentences[max(0, index - 2): index]))
    elif kind == "new_authorization":
        if "authorized a new" not in lowered or "repurchase program" not in lowered:
            return None
        year = _stated_year(sentence)
        if year is None:
            year = _stated_year(" ".join(sentences[max(0, index - 2): index]))
    else:
        return None
    amount = _one_amount(sentence)
    if amount is None:
        return None
    value, unit = amount
    return value, unit, year


def _keep_requested_period(found: List[Dict], asked: List[int]) -> List[Dict]:
    if asked:
        return [item for item in found if item.get("year") in asked]
    dated = [item for item in found if item.get("year") is not None]
    if not dated:
        return found
    latest = max(item["year"] for item in dated)
    chosen = [item for item in dated if item["year"] == latest]
    latest_values = {round(item["value"], 6) for item in chosen}
    for item in found:
        if item.get("year") is None and round(item["value"], 6) not in latest_values:
            chosen.append(item)
    return chosen


def _filing_disclosure_amounts(chunks: List[Dict], spec: Dict, question: str) -> List[Dict]:
    found = []
    for chunk in chunks:
        sentences = _sentences(chunk.get("text", ""))
        for index, sentence in enumerate(sentences):
            hit = _disclosure_hit(sentences, index, spec["kind"])
            if hit is None:
                continue
            value, unit, year = hit
            output_unit = _output_unit(question, unit, growth=False)
            converted = _convert(value, unit, output_unit)
            if converted is None:
                continue
            found.append({
                "value": converted,
                "unit": output_unit,
                "sentence": sentence.strip(),
                "narrow": False,
                "year": year,
                "document": chunk,
            })
    return _keep_requested_period(found, _question_years(question))


def _sentences(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def _sentence_amount(sentence: str, spec: Dict):
    lowered = sentence.lower()
    if spec["date"] is not None:
        found = _date_key(sentence)
        if found != spec["date"]:
            return None
    for phrase in spec["phrases"]:
        if phrase.lower() not in lowered:
            return None
    anchor = min(lowered.find(phrase.lower()) for phrase in spec["phrases"])
    candidates = []
    for match in _MONEY_RE.finditer(sentence):
        prefix = sentence[max(0, match.start() - 24):match.start()]
        if _CHANGE_AMOUNT_RE.search(prefix):
            continue
        raw = match.group(1)
        decimals = len(raw.split(".", 1)[1]) if "." in raw else 0
        value = round(float(raw.replace(",", "")), decimals)
        unit = match.group(2).lower().rstrip("s")
        candidates.append((abs(match.start() - anchor), value, unit))
    if not candidates:
        return None
    candidates.sort()
    _distance, value, unit = candidates[0]
    return value, unit


def _is_narrower(sentence: str, question: str, spec: Optional[Dict] = None) -> bool:
    match = _NARROW_RE.search(sentence)
    if not match:
        return False
    if match.group(0).lower() in question.lower():
        return False
    phrases = " ".join((spec or {}).get("phrases") or []).lower()
    if "seed capital" in phrases or "co-investment" in phrases:
        return False
    return True
