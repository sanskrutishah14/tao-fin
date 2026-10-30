"""Manual runner for the smoke test and the validation set.

Not imported by the API. Does not call Finnhub or Yahoo Finance.
Writes a percentage only when every question has traced gold and a finished answer.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

for _path in (PROJECT_ROOT, BACKEND_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from evaluation.scoring import answer_correct, is_abstention, summarize  # noqa: E402


SMOKE_LABEL = (
    "8-question local smoke test. Not an estimate of overall TAO-Fin accuracy."
)
VALIDATION_LABEL = (
    "Fixed validation set. Use only for before-and-after comparison. "
    "Not an estimate of overall financial answer accuracy."
)

_SETS = {
    "smoke": {
        "questions": PROJECT_ROOT / "evaluation" / "smoke_questions.json",
        "summary": RESULTS_DIR / "smoke_summary.json",
        "results": RESULTS_DIR / "smoke_results.json",
        "expected_total": 8,
        "label": SMOKE_LABEL,
    },
    "validation": {
        "questions": PROJECT_ROOT / "evaluation" / "validation_questions.json",
        "summary": RESULTS_DIR / "validation_baseline.json",
        "results": RESULTS_DIR / "validation_results.json",
        "expected_total": 12,
        "label": VALIDATION_LABEL,
    },
}


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_questions(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def trace_question(question: Dict[str, Any]) -> str | None:
    """Return a reason when gold cannot be read from the named filing."""

    if question.get("gold_value") is None and not question.get("gold_text"):
        return "gold value is empty"
    source = PROJECT_ROOT / str(question.get("source_file", ""))
    if not source.exists():
        return f"source filing not on disk: {source}"
    text = source.read_text(encoding="utf-8", errors="replace")
    quote = question.get("source_quote")
    if quote and _collapse(quote) not in _collapse(text):
        return "source quote is not in the filing"

    lines = [
        question.get("source_line"),
        question.get("source_line_extra"),
    ]
    lines = [line for line in lines if line]
    if lines:
        from app.services.table_parser import extract_table_chunks

        chunks = extract_table_chunks(
            str(source),
            metadata={"form": question.get("form"), "filing": source.name},
        )
        blob = "\n".join(chunk.get("text", "") for chunk in chunks)
        for line in lines:
            if line not in blob:
                return "table line is not in the parsed filing"
    return None


def blocked_summary(kind: str, reason: str) -> Dict[str, Any]:
    spec = _SETS[kind]
    return {
        "status": "blocked",
        "label": spec["label"],
        "expected_total": spec["expected_total"],
        "reason": reason,
    }


def ollama_reachable() -> str | None:
    import requests

    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        response = requests.get(f"{base}/api/tags", timeout=5)
    except Exception as exc:
        return f"Ollama is not reachable at {base}: {type(exc).__name__}"
    if not response.ok:
        return f"Ollama returned HTTP {response.status_code}"
    return None


def run_kind(
    kind: str,
    summary_path: Path | None = None,
    label: str | None = None,
) -> int:
    # The live app resolves data/sec and tao_fin.db relative to the
    # backend directory. Match that before opening the database.
    os.chdir(BACKEND_DIR)

    spec = _SETS[kind]
    questions = load_questions(spec["questions"])
    reasons = []
    for question in questions:
        reason = trace_question(question)
        if reason:
            reasons.append({"id": question.get("id"), "reason": reason})

    if len(questions) != spec["expected_total"] or reasons:
        summary = {
            "status": "incomplete",
            "label": spec["label"],
            "expected_total": spec["expected_total"],
            "reasons": reasons
            or [
                {
                    "id": None,
                    "reason": (
                        f"expected {spec['expected_total']} questions, "
                        f"found {len(questions)}"
                    ),
                }
            ],
        }
        _write(spec["summary"], summary)
        print(f"{kind}: incomplete. No accuracy written.")
        for item in summary["reasons"]:
            print(f"  {item['id']}: {item['reason']}")
        return 2

    ollama_error = ollama_reachable()
    if ollama_error:
        _write(spec["summary"], blocked_summary(kind, ollama_error))
        print(f"{kind}: blocked. {ollama_error}")
        return 3

    from app.services.rag_index import build_tao_pipeline

    pipeline, _indexed = build_tao_pipeline()
    if pipeline is None:
        reason = "SEC index is empty. No synced filings were available to build the pipeline."
        _write(spec["summary"], blocked_summary(kind, reason))
        print(f"{kind}: blocked. {reason}")
        return 3

    pipeline.allow_external_fallback = False
    results = []
    for question in questions:
        item = {
            "id": question["id"],
            "question": question["question"],
            "expected_path": question.get("expected_path"),
            "category": question.get("category"),
            "availability": "available",
            "ran": False,
        }
        try:
            output = pipeline.run(question["question"])
        except Exception as exc:
            item["reason"] = f"{type(exc).__name__}: {exc}"
            results.append(item)
            continue
        prediction = output.get("answer", "")
        item["ran"] = True
        item["predicted_answer"] = prediction
        item["abstained"] = is_abstention(prediction)
        item["answer_correct"] = answer_correct(prediction, question)
        verification = output.get("verification") or {}
        item["verifier_confidence"] = verification.get("confidence")
        item["latency_seconds"] = output.get("latency_seconds")
        results.append(item)
        print(
            f"{item['id']}: correct={item['answer_correct']} "
            f"latency={item['latency_seconds']} "
            f"confidence={item['verifier_confidence']}"
        )

    if any(not item.get("ran") for item in results):
        summary = {
            "status": "incomplete",
            "label": label or spec["label"],
            "expected_total": spec["expected_total"],
            "reasons": [
                {
                    "id": item.get("id"),
                    "reason": item.get("reason", "question did not finish"),
                }
                for item in results
                if not item.get("ran")
            ],
        }
    else:
        summary = summarize(
            results,
            expected_total=spec["expected_total"],
            label=label or spec["label"],
        )

    if summary_path is None:
        _write(spec["results"], {"items": results})
        _write(spec["summary"], summary)
    else:
        _write(summary_path, summary)
    if summary.get("status") == "complete":
        print(
            f"{kind}: {summary['correct']} / {summary['total']} "
            f"({summary['accuracy']:.1%})"
        )
        return 0
    print(f"{kind}: {summary['status']}. No accuracy published.")
    return 2


def main_for(kind: str) -> int:
    if kind not in _SETS:
        print(f"Unknown set {kind}")
        return 1
    return run_kind(kind)
