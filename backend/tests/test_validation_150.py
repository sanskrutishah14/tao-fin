"""Checks for the 150-question development set.

Run from the backend directory:

    python tests/test_validation_150.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from evaluation.validation_150 import PROJECT_ROOT, verify_questions


RESULTS = []
QUESTIONS = PROJECT_ROOT / "evaluation" / "validation_150_questions.json"
EARLIER = (
    "smoke_questions.json",
    "validation_questions.json",
    "validation_50_questions.json",
)


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


def main():
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    record("file has 150 questions", len(questions) == 150, str(len(questions)))
    ids = [item["id"] for item in questions]
    record(
        "ids are dev-001 through dev-150",
        ids == [f"dev-{index:03d}" for index in range(1, 151)],
    )
    earlier = set()
    for name in EARLIER:
        payload = json.loads((PROJECT_ROOT / "evaluation" / name).read_text(encoding="utf-8"))
        earlier.update(item["question"].strip().lower() for item in payload)
    copied = [item["id"] for item in questions if item["question"].strip().lower() in earlier]
    record("no question text is copied from the earlier sets", not copied, str(copied[:5]))
    required = {
        "ticker",
        "company",
        "fiscal_year",
        "accession",
        "source_file",
        "source_quote",
        "category",
    }
    missing = [
        item["id"]
        for item in questions
        if not required <= set(item) or not item.get("source_quote")
    ]
    record("each question records company, period, filing, accession, and quote", not missing, str(missing[:5]))
    categories = {item["category"] for item in questions}
    needed = {
        "lookup",
        "ratio",
        "growth",
        "unit_conversion",
        "comparison",
        "narrative",
        "insufficient_evidence",
    }
    record("required categories are present", needed <= categories, str(sorted(categories)))
    abstain = [
        item for item in questions
        if item["category"] == "insufficient_evidence"
    ]
    record(
        "insufficient-evidence questions expect abstention and have no invented number",
        bool(abstain) and all(
            item.get("expected_answer") == "abstain" and item.get("gold_value") is None
            for item in abstain
        ),
        str(len(abstain)),
    )
    numbered = [
        item for item in questions
        if item["category"] != "insufficient_evidence"
    ]
    record(
        "every other question has a numeric gold value and unit",
        all(item.get("gold_value") is not None and item.get("gold_unit") for item in numbered),
    )
    reasons = verify_questions(questions)
    record("every quote and table line is in the named filing", not reasons, "; ".join(reasons[:5]))


if __name__ == "__main__":
    main()
    failed = [item for item in RESULTS if not item[1]]
    print(f"passed={len(RESULTS) - len(failed)} failed={len(failed)}")
    raise SystemExit(1 if failed else 0)
