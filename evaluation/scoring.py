"""Exact scoring for the local smoke test and validation set.

Accuracy is correct/total against traced gold values. Verifier confidence
is never an input.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional


_CITATION_RE = re.compile(r"evidence\s+\d+", re.IGNORECASE)

_TOKEN_RE = re.compile(
    r"(-)?\$?\s*(\d[\d,]*(?:\.\d+)?)\s*"
    r"(billion|million|millions|thousand|thousands|percent|%)?",
    re.IGNORECASE,
)

_SCALE = {
    "thousand": 1_000.0,
    "thousands": 1_000.0,
    "million": 1_000_000.0,
    "millions": 1_000_000.0,
    "billion": 1_000_000_000.0,
}

_MONEY_UNITS = {"thousand", "thousands", "million", "millions", "billion"}


def _is_year(value: float) -> bool:
    return value == int(value) and 1990 <= int(value) <= 2035


def _canonical_unit(unit: Optional[str]) -> Optional[str]:
    if unit is None:
        return None
    unit = unit.lower()
    if unit in {"million", "millions"}:
        return "million"
    if unit in {"thousand", "thousands"}:
        return "thousand"
    if unit == "billion":
        return "billion"
    if unit in {"percent", "%"}:
        return "percent"
    return unit


def extract_primary_number(text: str) -> Optional[Dict[str, Any]]:
    """Pick the asserted figure, ignoring a bare fiscal year when another number exists."""

    if not text:
        return None

    text = _CITATION_RE.sub(" ", str(text))

    candidates = []
    for match in _TOKEN_RE.finditer(text):
        raw = match.group(2).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if match.group(1):
            value = -value
        candidates.append(
            {
                "value": value,
                "unit": _canonical_unit(match.group(3)),
            }
        )

    if not candidates:
        return None

    non_years = [item for item in candidates if not _is_year(item["value"])]
    pool = non_years or candidates
    with_unit = [item for item in pool if item["unit"]]
    if with_unit:
        return with_unit[-1]
    return pool[-1]


def is_abstention(text: str) -> bool:
    return "insufficient evidence" in str(text or "").lower()


def _to_gold_unit(
    value: float,
    answer_unit: Optional[str],
    gold_unit: str,
    allow_scale: bool,
) -> Optional[float]:
    gold_unit = _canonical_unit(gold_unit) or gold_unit
    answer_unit = _canonical_unit(answer_unit)

    if gold_unit == "percent":
        if answer_unit not in {None, "percent"}:
            return None
        return value

    if gold_unit == "usd_per_share":
        if answer_unit in _MONEY_UNITS:
            return None
        return value

    if gold_unit not in _SCALE:
        return None

    if answer_unit is None:
        return value

    if answer_unit not in _SCALE:
        return None

    if answer_unit != gold_unit and not allow_scale:
        return None

    return value * _SCALE[answer_unit] / _SCALE[gold_unit]


def _gold_decimals(gold: float) -> int:
    """Decimal places in the stored gold figure. Integers stay exact."""

    text = f"{gold:.6f}".rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1])


def _round_half_up(value: float, decimals: int) -> float:
    factor = 10 ** decimals
    scaled = value * factor
    if scaled >= 0:
        rounded = math.floor(scaled + 0.5)
    else:
        rounded = math.ceil(scaled - 0.5)
    return rounded / factor


def answer_correct(prediction: str, question: Dict[str, Any]) -> bool:
    """Compare one prediction with one question's stored gold rule."""

    if is_abstention(prediction):
        return False

    if question.get("answer_mode") == "text":
        expected = " ".join(str(question.get("gold_text", "")).lower().split())
        actual = " ".join(str(prediction or "").lower().split())
        return bool(expected) and actual == expected

    parsed = extract_primary_number(prediction)
    if parsed is None or question.get("gold_value") is None:
        return False

    converted = _to_gold_unit(
        parsed["value"],
        parsed["unit"],
        str(question.get("gold_unit")),
        bool(question.get("allow_scale_conversion", False)),
    )
    if converted is None:
        return False

    gold = float(question["gold_value"])
    tolerance_mode = question.get("tolerance_mode", "exact")
    if tolerance_mode == "absolute":
        return abs(converted - gold) <= float(question.get("tolerance_abs", 0.0))
    if tolerance_mode == "relative":
        denom = max(abs(gold), 1.0)
        return abs(converted - gold) / denom <= float(question.get("tolerance", 0.0))
    if abs(converted - gold) <= 1e-6:
        return True
    # A fractional gold figure such as 91.3 is already rounded to that many
    # places. After unit conversion, the same amount at finer precision matches.
    # Integer gold stays exact, so a nearby wrong number does not pass.
    decimals = _gold_decimals(gold)
    if decimals < 1:
        return False
    return abs(_round_half_up(converted, decimals) - gold) <= 1e-6


def summarize(
    results: List[Dict[str, Any]],
    *,
    expected_total: int,
    label: str,
) -> Dict[str, Any]:
    """A percentage exists only when every item ran against traced gold."""

    reasons = []
    for result in results:
        if result.get("availability") != "available":
            reasons.append(
                {
                    "id": result.get("id"),
                    "reason": result.get("reason") or "source filing or gold value unavailable",
                }
            )
        elif result.get("ran") is not True:
            reasons.append(
                {
                    "id": result.get("id"),
                    "reason": result.get("reason") or "question was not run",
                }
            )

    base: Dict[str, Any] = {
        "label": label,
        "expected_total": expected_total,
        "items": results,
    }

    if len(results) != expected_total or reasons:
        base["status"] = "incomplete"
        base["reasons"] = reasons
        return base

    correct = sum(1 for result in results if result.get("answer_correct") is True)
    abstained = sum(1 for result in results if result.get("abstained") is True)
    base.update(
        {
            "status": "complete",
            "correct": correct,
            "total": expected_total,
            "accuracy": correct / expected_total,
            "abstained": abstained,
        }
    )
    return base
