"""Sequential runner for the independent 50-question evaluation.

Builds the SEC index once, runs a five-question pilot, then the rest.
Saves after every question. Does not call Finnhub or Yahoo Finance.
Does not write validation_baseline.json or validation_after_table_lookup.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "validation_50_questions.json"
PILOT_PATH = RESULTS_DIR / "validation_50_pilot.json"
BASELINE_PATH = RESULTS_DIR / "validation_50_baseline.json"
PROTECTED = (
    RESULTS_DIR / "validation_baseline.json",
    RESULTS_DIR / "validation_after_table_lookup.json",
)

for _path in (PROJECT_ROOT, BACKEND_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from evaluation.local_eval import (  # noqa: E402
    load_questions,
    ollama_reachable,
    trace_question,
)
from evaluation.scoring import answer_correct, is_abstention, summarize  # noqa: E402
from evaluation.validation_50 import LABEL  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _working_set_mb() -> float | None:
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        )
        if not ok:
            return None
        return round(counters.WorkingSetSize / (1024 * 1024), 1)
    except Exception:
        return None


def _write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if path.name in {"validation_baseline.json", "validation_after_table_lookup.json"}:
        raise RuntimeError(f"refusing to write protected file {path}")


def _latency_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    values = sorted(
        float(item["latency_seconds"])
        for item in items
        if item.get("latency_seconds") is not None
    )
    if not values:
        return {}

    def pick(fraction: float) -> float:
        index = min(len(values) - 1, max(0, round(fraction * (len(values) - 1))))
        return values[index]

    return {
        "count": len(values),
        "min_seconds": values[0],
        "median_seconds": pick(0.5),
        "p90_seconds": pick(0.9),
        "max_seconds": values[-1],
        "mean_seconds": round(sum(values) / len(values), 2),
    }


def _score_one(question: Dict[str, Any], pipeline) -> Dict[str, Any]:
    item = {
        "id": question["id"],
        "question": question["question"],
        "category": question.get("category"),
        "ticker": question.get("ticker"),
        "availability": "available",
        "ran": False,
    }
    started = time.perf_counter()
    try:
        output = pipeline.run(question["question"])
    except Exception as exc:
        item["reason"] = f"{type(exc).__name__}: {exc}"
        item["latency_seconds"] = round(time.perf_counter() - started, 2)
        return item
    prediction = output.get("answer", "")
    item["ran"] = True
    item["predicted_answer"] = prediction
    item["abstained"] = is_abstention(prediction)
    item["answer_correct"] = answer_correct(prediction, question)
    verification = output.get("verification") or {}
    item["verifier_confidence"] = verification.get("confidence")
    item["latency_seconds"] = output.get("latency_seconds")
    item["working_set_mb"] = _working_set_mb()
    return item


def _publish(path: Path, items: List[Dict[str, Any]], *, expected: int, resources: List[Dict[str, Any]], note: str, label: str = LABEL) -> Dict[str, Any]:
    finished = [item for item in items if item.get("ran")]
    if len(items) == expected and len(finished) == expected:
        summary = summarize(items, expected_total=expected, label=label)
    else:
        summary = {
            "status": "incomplete",
            "label": label,
            "expected_total": expected,
            "items": items,
            "reasons": [
                {"id": item.get("id"), "reason": item.get("reason", "question did not finish")}
                for item in items
                if not item.get("ran")
            ],
        }
    summary["resources"] = resources
    summary["latency_distribution"] = _latency_summary(finished)
    summary["note"] = note
    _write(path, summary)
    return summary


BATCH1_LABEL = (
    "50-question development set after Batch 1 correctness safeguards. "
    "Same questions as validation_50_baseline.json. Not an estimate of "
    "overall financial accuracy."
)
BLOCKED_OUTPUTS = {
    "validation_baseline.json",
    "validation_after_table_lookup.json",
    "validation_50_baseline.json",
    "validation_50_pilot.json",
    "validation_50_after_batch1.json",
    "validation_50_after_batch2.json",
    "validation_50_after_batch3.json",
    "validation_results.json",
    "smoke_results.json",
    "smoke_summary.json",
}
BATCH2_LABEL = (
    "50-question development set after Batch 2 table-caption scale extraction. "
    "Same questions and gold values as validation_50_baseline.json. "
    "Not an estimate of overall financial accuracy."
)
BATCH3_LABEL = (
    "50-question development set after Batch 3 deterministic calculations. "
    "Same questions and gold values as validation_50_baseline.json. "
    "Not an estimate of overall financial accuracy. "
    "Scoring accepts a fractional gold amount after explicit unit conversion "
    "when it rounds half-up to the gold figure's decimal places."
)
BATCH4_LABEL = (
    "50-question development set after Batch 4 narrative evidence matching. "
    "Same questions and gold values as validation_50_baseline.json. "
    "Not an estimate of overall financial accuracy. "
    "Scoring is the Batch 3 revised rule."
)


def main(output_path: Path | None = None) -> int:
    os.chdir(BACKEND_DIR)
    full_path = output_path or BASELINE_PATH
    pilot_path = None if output_path else PILOT_PATH
    if output_path is None:
        label = LABEL
    elif "batch4" in output_path.name:
        label = BATCH4_LABEL
    elif "batch3" in output_path.name:
        label = BATCH3_LABEL
    elif "batch2" in output_path.name:
        label = BATCH2_LABEL
    else:
        label = BATCH1_LABEL
    watched = list(PROTECTED)
    if output_path is not None:
        watched.extend([
            BASELINE_PATH,
            PILOT_PATH,
            RESULTS_DIR / "validation_50_after_batch1.json",
            RESULTS_DIR / "validation_50_after_batch2.json",
            RESULTS_DIR / "validation_50_after_batch3.json",
        ])
    protected = {str(path): _sha256(path) for path in watched if path.exists()}
    questions = load_questions(QUESTIONS_PATH)
    if len(questions) != 50:
        print(f"expected 50 questions, found {len(questions)}")
        return 2

    reasons = []
    for question in questions:
        reason = trace_question(question)
        if reason:
            reasons.append({"id": question["id"], "reason": reason})
    if reasons:
        summary = {
            "status": "incomplete",
            "label": LABEL,
            "expected_total": 50,
            "reasons": reasons,
        }
        summary["label"] = label
        _write(full_path, summary)
        print("trace failed. No accuracy published.")
        for item in reasons:
            print(f"  {item['id']}: {item['reason']}")
        return 2

    ollama_error = ollama_reachable()
    resources = [{"stage": "start", "working_set_mb": _working_set_mb()}]
    if ollama_error:
        _write(
            full_path,
            {
                "status": "blocked",
                "label": label,
                "expected_total": 50,
                "reason": ollama_error,
                "resources": resources,
            },
        )
        print(f"blocked. {ollama_error}")
        return 3

    from app.services.rag_index import build_tao_pipeline

    pipeline, _indexed = build_tao_pipeline()
    resources.append({"stage": "index", "working_set_mb": _working_set_mb()})
    if pipeline is None:
        _write(
            full_path,
            {
                "status": "blocked",
                "label": label,
                "expected_total": 50,
                "reason": "SEC index is empty.",
                "resources": resources,
            },
        )
        print("blocked. SEC index is empty.")
        return 3

    pipeline.allow_external_fallback = False
    pilot_items = []
    for question in questions[:5]:
        item = _score_one(question, pipeline)
        pilot_items.append(item)
        print(
            f"{item['id']}: ran={item['ran']} correct={item.get('answer_correct')} "
            f"latency={item.get('latency_seconds')} ws_mb={item.get('working_set_mb')}"
        )
        if pilot_path is not None:
            _publish(
                pilot_path,
                pilot_items,
                expected=5,
                resources=resources,
                note="Five-question pilot. Not the 50-question baseline.",
                label=label,
            )
        else:
            _publish(
                full_path,
                pilot_items,
                expected=50,
                resources=resources,
                note="Pilot portion. Full set still running.",
                label=label,
            )
    resources.append({"stage": "pilot", "working_set_mb": _working_set_mb()})
    if not all(item.get("ran") for item in pilot_items):
        _publish(
            full_path,
            pilot_items,
            expected=50,
            resources=resources,
            note="Pilot did not finish every question. Full set was not started.",
            label=label,
        )
        print("pilot incomplete. Full set was not started.")
        return 2

    items = list(pilot_items)
    for question in questions[5:]:
        item = _score_one(question, pipeline)
        items.append(item)
        print(
            f"{item['id']}: ran={item['ran']} correct={item.get('answer_correct')} "
            f"latency={item.get('latency_seconds')} ws_mb={item.get('working_set_mb')}"
        )
        _publish(
            full_path,
            items,
            expected=50,
            resources=resources,
            note=f"{label} Partial until status is complete.",
            label=label,
        )

    resources.append({"stage": "end", "working_set_mb": _working_set_mb()})
    summary = _publish(
        full_path,
        items,
        expected=50,
        resources=resources,
        note=label,
        label=label,
    )
    for path_key, digest in protected.items():
        if _sha256(Path(path_key)) != digest:
            raise RuntimeError(f"protected file changed: {path_key}")
    if summary.get("status") == "complete":
        print(
            f"validation_50: {summary['correct']} / {summary['total']} "
            f"({summary['accuracy']:.1%})"
        )
        return 0
    print(f"validation_50: {summary['status']}. No accuracy published.")
    return 2


if __name__ == "__main__":
    chosen = None
    if len(sys.argv) > 1:
        chosen = Path(sys.argv[1])
        if not chosen.is_absolute():
            chosen = PROJECT_ROOT / chosen
        if chosen.name in BLOCKED_OUTPUTS:
            print(f"refusing to overwrite {chosen.name}")
            raise SystemExit(2)
    raise SystemExit(main(chosen))
