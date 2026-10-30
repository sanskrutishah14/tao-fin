"""Checks for the independent 50-question file.

Does not call the answering pipeline or Ollama.

    python tests/test_validation_50.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

from evaluation.scoring import answer_correct

results = []


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


questions = json.loads(
    (PROJECT / "evaluation" / "validation_50_questions.json").read_text(encoding="utf-8")
)
smoke = json.loads(
    (PROJECT / "evaluation" / "smoke_questions.json").read_text(encoding="utf-8")
)
validation = json.loads(
    (PROJECT / "evaluation" / "validation_questions.json").read_text(encoding="utf-8")
)
prior = {item["question"] for item in smoke + validation}

record("file has 50 questions", len(questions) == 50, str(len(questions)))
record("ids are ind-01 through ind-50", [item["id"] for item in questions] == [f"ind-{i:02d}" for i in range(1, 51)])
record(
    "no question text is copied from smoke or validation",
    not any(item["question"] in prior for item in questions),
)
record(
    "every question has company, year, accession, gold, and unit",
    all(
        item.get("ticker")
        and item.get("fiscal_year")
        and item.get("accession")
        and item.get("gold_value") is not None
        and item.get("gold_unit")
        and item.get("source_file")
        for item in questions
    ),
)


def sample(item):
    value = item["gold_value"]
    unit = item["gold_unit"]
    if unit == "percent":
        return f"{value}%"
    if unit == "usd_per_share":
        return str(value)
    if isinstance(value, float) and abs(value - round(value)) > 1e-6:
        text = f"{value:.6f}".rstrip("0").rstrip(".")
    else:
        text = f"{int(round(value)):,}"
    return f"{text} {unit}" if unit in {"million", "billion"} else text


mismatches = [
    item["id"]
    for item in questions
    if not answer_correct(sample(item), item)
]
record("a correctly formatted gold answer scores correct", not mismatches, str(mismatches))

categories = {item["category"] for item in questions}
record(
    "set includes lookups, ratios, growth, unit conversion, comparison, and narrative",
    categories >= {"lookup", "ratio", "growth", "unit_conversion", "comparison", "narrative"},
    str(sorted(categories)),
)

if __name__ == "__main__":
    failed = [name for name, passed, _detail in results if not passed]
    print(f"\npassed={sum(1 for _n, ok, _d in results if ok)} failed={len(failed)}")
    if failed:
        sys.exit(1)
