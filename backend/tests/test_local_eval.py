"""Scorer and read-only eval endpoints.

Run from the backend directory:

    python tests/test_local_eval.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.eval_status import router as eval_router
from evaluation.local_eval import load_questions, trace_question
from evaluation.scoring import answer_correct, summarize

results = []


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


million_question = {
    "gold_value": 1577,
    "gold_unit": "million",
    "allow_scale_conversion": True,
    "tolerance_mode": "exact",
    "answer_mode": "numeric",
}

record(
    "1577 million rejects 1.7 billion",
    answer_correct("$1.7 billion", million_question) is False,
)
record(
    "1577 million accepts $1,577 million",
    answer_correct("3M capex was $1,577 million", million_question) is True,
)
notes = {
    "gold_value": 91.3,
    "gold_unit": "billion",
    "allow_scale_conversion": True,
    "tolerance_mode": "exact",
    "answer_mode": "numeric",
}
record(
    "91,281 million rounds to the disclosed 91.3 billion",
    answer_correct("aggregate principal was 91,281 million", notes) is True,
)
record(
    "91.281 billion rounds to 91.3 billion",
    answer_correct("91.281 billion", notes) is True,
)
record(
    "91.0 billion does not round to 91.3 billion",
    answer_correct("91.0 billion", notes) is False,
)
record(
    "678 billion does not match 28.9 billion",
    answer_correct(
        "$678 billion",
        {
            "gold_value": 28.9,
            "gold_unit": "billion",
            "allow_scale_conversion": True,
            "tolerance_mode": "exact",
            "answer_mode": "numeric",
        },
    ) is False,
)
record(
    "an integer gold value does not accept a nearby number",
    answer_correct("1,577.4 million", million_question) is False,
)
record(
    "confidence is not an input to answer_correct",
    answer_correct("$1.7 billion", {**million_question, "verifier_confidence": 1.0}) is False,
)

ratio_question = {
    "gold_value": 31.20,
    "gold_unit": "percent",
    "tolerance_mode": "absolute",
    "tolerance_abs": 0.01,
    "answer_mode": "numeric",
}
record("ratio 31.20 within 0.01", answer_correct("31.20%", ratio_question) is True)
record("ratio 31.5 outside 0.01", answer_correct("31.5%", ratio_question) is False)
record(
    "abstention is not correct",
    answer_correct("Insufficient evidence.", million_question) is False,
)

per_share = {
    "gold_value": 7.46,
    "gold_unit": "usd_per_share",
    "allow_scale_conversion": False,
    "tolerance_mode": "exact",
    "answer_mode": "numeric",
}
record(
    "per-share rejects an explicit million unit",
    answer_correct("7.46 million", per_share) is False,
)
record("per-share accepts 7.46", answer_correct("diluted EPS was 7.46", per_share) is True)

negative_percent = {
    "gold_value": -30.78,
    "gold_unit": "percent",
    "allow_scale_conversion": False,
    "tolerance_mode": "absolute",
    "tolerance_abs": 0.01,
    "answer_mode": "numeric",
}
record(
    "negative percent keeps the minus on the result",
    answer_correct(
        "The growth rate was -30.78%. It was calculated as (20,935 - 30,242) / 30,242, multiplied by 100.",
        negative_percent,
    )
    is True,
)
record(
    "a positive percent does not match a negative gold value",
    answer_correct(
        "The growth rate was 30.78%. It was calculated as (20,935 - 30,242) / 30,242, multiplied by 100.",
        negative_percent,
    )
    is False,
)
record(
    "a nearby negative percent is outside 0.01",
    answer_correct("The growth rate was -30.70%.", negative_percent) is False,
)
negative_money = {
    "gold_value": -8,
    "gold_unit": "million",
    "allow_scale_conversion": True,
    "tolerance_mode": "exact",
    "answer_mode": "numeric",
}
record(
    "negative millions keep the minus on the result",
    answer_correct(
        "The change was -8 million. It was calculated as 24 - 32.",
        negative_money,
    )
    is True,
)
record(
    "the unsigned amount does not match negative millions",
    answer_correct("The change was 8 million. It was calculated as 24 - 32.", negative_money) is False,
)
record(
    "a different negative magnitude does not match",
    answer_correct("The change was -32 million. It was calculated as 24 - 32.", negative_money) is False,
)
positive_growth = {
    "gold_value": 4.8,
    "gold_unit": "percent",
    "allow_scale_conversion": False,
    "tolerance_mode": "absolute",
    "tolerance_abs": 0.01,
    "answer_mode": "numeric",
}
record(
    "a positive result ignores an unrelated minus in the formula",
    answer_correct(
        "The growth rate was 4.80%. It was calculated as (194,116 - 185,233) / 185,233, multiplied by 100.",
        positive_growth,
    )
    is True,
)
record(
    "a negative result does not match a positive gold value",
    answer_correct("The growth rate was -4.80%.", positive_growth) is False,
)
record(
    "Evidence 1 is not treated as the answer",
    answer_correct(
        "Microsoft's diluted earnings per share for fiscal year 2026 was 17.95, which was derived from the evidence in Evidence 1.",
        {
            "gold_value": 17.95,
            "gold_unit": "usd_per_share",
            "allow_scale_conversion": False,
            "tolerance_mode": "exact",
            "answer_mode": "numeric",
        },
    )
    is True,
)

complete = summarize(
    [
        {"id": f"q{i}", "availability": "available", "ran": True, "answer_correct": i < 2, "abstained": False}
        for i in range(8)
    ],
    expected_total=8,
    label="smoke",
)
record(
    "2 of 8 is accuracy 0.25",
    complete["status"] == "complete" and complete["correct"] == 2 and complete["total"] == 8 and complete["accuracy"] == 0.25,
    str({k: complete[k] for k in ("status", "correct", "total", "accuracy")}),
)

incomplete = summarize(
    [{"id": "q1", "availability": "unavailable", "ran": False, "reason": "filing missing"}],
    expected_total=8,
    label="smoke",
)
record(
    "unavailable item omits accuracy",
    incomplete["status"] == "incomplete" and "accuracy" not in incomplete,
)

for name in ("smoke_questions.json", "validation_questions.json"):
    path = PROJECT / "evaluation" / name
    questions = load_questions(path)
    expected = 8 if "smoke" in name else 12
    reasons = [f"{q['id']}: {trace_question(q)}" for q in questions if trace_question(q)]
    record(
        f"{name} traces to on-disk filings",
        len(questions) == expected and not reasons,
        "; ".join(reasons) if reasons else f"count={len(questions)}",
    )

with tempfile.TemporaryDirectory() as tmp:
    os.environ["TAO_EVAL_RESULTS_DIR"] = tmp
    app = FastAPI()
    app.include_router(eval_router)
    client = TestClient(app)

    missing = client.get("/api/eval/smoke")
    body = missing.json()
    record(
        "missing summary is not_run without accuracy",
        missing.status_code == 200 and body.get("status") == "not_run" and "accuracy" not in body,
        str(body),
    )

    smoked = Path(tmp) / "smoke_summary.json"
    smoked.write_text(
        json.dumps(
            {
                "status": "complete",
                "correct": 2,
                "total": 8,
                "accuracy": 0.25,
                "items": [{"id": "smoke-01", "expected_path": "deterministic_ratio_no_llm", "latency_seconds": 0.2}],
            }
        ),
        encoding="utf-8",
    )
    present = client.get("/api/eval/smoke").json()
    record(
        "complete smoke summary returns 2/8 and 0.25",
        present.get("correct") == 2 and present.get("total") == 8 and present.get("accuracy") == 0.25,
        str({k: present.get(k) for k in ("correct", "total", "accuracy", "status")}),
    )

    (Path(tmp) / "validation_baseline.json").write_text(
        json.dumps({"status": "incomplete", "accuracy": 0.99, "correct": 12, "total": 12, "reasons": [{"id": "valid-01", "reason": "missing"}]}),
        encoding="utf-8",
    )
    validation = client.get("/api/eval/validation").json()
    record(
        "incomplete validation strips a stored percentage",
        validation.get("status") == "incomplete" and "accuracy" not in validation and "correct" not in validation,
        str(validation),
    )

    del os.environ["TAO_EVAL_RESULTS_DIR"]

print()
passed = sum(1 for _, flag, _ in results if flag is True)
failed = sum(1 for _, flag, _ in results if flag is False)
print(f"passed={passed} failed={failed}")
sys.exit(1 if failed else 0)
