"""Sequential runner for the 150-question development set.

Builds the SEC index once per invocation, saves after every question, and
skips questions that already finished in the output file. Does not call
Finnhub or Yahoo Finance. Does not write any earlier result file.
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
QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "validation_150_questions.json"
OUTPUT_PATH = RESULTS_DIR / "validation_150_baseline.json"
PILOT_PATH = RESULTS_DIR / "validation_150_pilot.json"

for _path in (PROJECT_ROOT, BACKEND_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from evaluation.local_eval import ollama_reachable  # noqa: E402
from evaluation.scoring import answer_correct, is_abstention, summarize  # noqa: E402
from evaluation.validation_150 import LABEL, verify_questions  # noqa: E402


BLOCKED_OUTPUTS = {
    "validation_baseline.json",
    "validation_after_table_lookup.json",
    "validation_50_baseline.json",
    "validation_50_pilot.json",
    "validation_50_after_batch1.json",
    "validation_50_after_batch2.json",
    "validation_50_after_batch3.json",
    "validation_50_after_batch4.json",
    "validation_results.json",
    "smoke_results.json",
    "smoke_summary.json",
    "validation_150_baseline.json",
    "validation_150_pilot.json",
    "validation_150_scoring_audit.json",
    "validation_150_signed_rescore.json",
}
PROTECTED = [RESULTS_DIR / name for name in sorted(BLOCKED_OUTPUTS)]


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
    if path.name in BLOCKED_OUTPUTS:
        raise RuntimeError(f"refusing to write protected file {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def _category_summary(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    summary: Dict[str, Dict[str, int]] = {}
    for item in items:
        bucket = summary.setdefault(
            str(item.get("category") or "unspecified"),
            {"ran": 0, "correct": 0, "incorrect": 0, "abstained": 0},
        )
        if not item.get("ran"):
            continue
        bucket["ran"] += 1
        if item.get("abstained"):
            bucket["abstained"] += 1
        if item.get("answer_correct"):
            bucket["correct"] += 1
        else:
            bucket["incorrect"] += 1
    return summary


def _finished(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    found = {}
    for item in payload.get("items") or []:
        if item.get("ran") is True and item.get("id"):
            found[str(item["id"])] = item
    return found


def _score_one(question: Dict[str, Any], pipeline) -> Dict[str, Any]:
    item = {
        "id": question["id"],
        "question": question["question"],
        "category": question.get("category"),
        "ticker": question.get("ticker"),
        "expected_answer": question.get("expected_answer"),
        "availability": "available",
        "ran": False,
    }
    started = time.perf_counter()
    try:
        output = pipeline.run(question["question"])
    except Exception as exc:
        item["reason"] = f"{type(exc).__name__}: {exc}"
        item["latency_seconds"] = round(time.perf_counter() - started, 2)
        item["working_set_mb"] = _working_set_mb()
        return item
    prediction = output.get("answer", "")
    item["ran"] = True
    item["predicted_answer"] = prediction
    item["abstained"] = is_abstention(prediction)
    item["answer_correct"] = answer_correct(prediction, question)
    if question.get("expected_answer") == "abstain":
        item["appropriate_abstention"] = bool(item["abstained"])
    verification = output.get("verification") or {}
    item["verifier_confidence"] = verification.get("confidence")
    item["latency_seconds"] = output.get("latency_seconds")
    item["working_set_mb"] = _working_set_mb()
    return item


def _publish(
    path: Path,
    items: List[Dict[str, Any]],
    *,
    expected: int,
    resources: List[Dict[str, Any]],
    note: str,
    label: str = LABEL,
    questions_sha256: str | None = None,
) -> Dict[str, Any]:
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
    summary["categories"] = _category_summary(finished)
    summary["appropriate_abstentions"] = sum(
        1 for item in finished if item.get("appropriate_abstention") is True
    )
    summary["note"] = note
    if questions_sha256:
        summary["questions_sha256"] = questions_sha256
    _write(path, summary)
    return summary


def main(max_new: int | None = None, snapshot_pilot: bool = False) -> int:
    os.chdir(BACKEND_DIR)
    if OUTPUT_PATH.name in BLOCKED_OUTPUTS:
        print(f"refusing to overwrite {OUTPUT_PATH.name}")
        return 2
    questions_bytes = QUESTIONS_PATH.read_bytes()
    questions = json.loads(questions_bytes.decode("utf-8"))
    questions_sha256 = hashlib.sha256(questions_bytes).hexdigest()
    expected = len(questions)
    prior_payload = {}
    if OUTPUT_PATH.exists():
        prior_payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    if prior_payload.get("questions_sha256") != questions_sha256:
        reasons = verify_questions(questions)
        if reasons:
            print("question verification failed. No evaluation started.")
            for reason in reasons[:20]:
                print(reason)
            return 2

    protected = {str(path): _sha256(path) for path in PROTECTED if path.exists()}
    done = {}
    if prior_payload.get("questions_sha256") == questions_sha256:
        done = _finished(OUTPUT_PATH)
    pending = [question for question in questions if question["id"] not in done]
    if not pending:
        print(f"validation_150 already has {len(done)} finished question(s).")
        return 0
    batch = pending if not max_new or max_new < 0 else pending[:max_new]

    ollama_error = ollama_reachable()
    resources = [{"stage": "start", "working_set_mb": _working_set_mb()}]
    if ollama_error:
        print(f"blocked. {ollama_error}")
        return 3

    from app.services.rag_index import build_tao_pipeline

    pipeline, _indexed = build_tao_pipeline()
    resources.append({"stage": "index", "working_set_mb": _working_set_mb()})
    if pipeline is None:
        print("blocked. SEC index is empty.")
        return 3
    pipeline.allow_external_fallback = False

    ordered = {question["id"]: question for question in questions}
    items = [done[question["id"]] for question in questions if question["id"] in done]
    for question in batch:
        item = _score_one(question, pipeline)
        items.append(item)
        items.sort(key=lambda row: ordered[row["id"]]["id"] if False else row["id"])
        print(
            f"{item['id']}: ran={item['ran']} correct={item.get('answer_correct')} "
            f"abstained={item.get('abstained')} latency={item.get('latency_seconds')} "
            f"ws_mb={item.get('working_set_mb')}"
        )
        note = (
            f"{LABEL} Partial until status is complete. "
            f"Finished {sum(1 for row in items if row.get('ran'))} of {expected}."
        )
        _publish(
            OUTPUT_PATH,
            items,
            expected=expected,
            resources=resources,
            note=note,
            questions_sha256=questions_sha256,
        )
        if snapshot_pilot and not PILOT_PATH.exists() and len(items) >= 8:
            pilot_items = sorted(items, key=lambda row: row["id"])[:8]
            _publish(
                PILOT_PATH,
                pilot_items,
                expected=8,
                resources=resources,
                note="Eight-question pilot of the 150-question development set. Not the full baseline.",
                label="Eight-question pilot of the 150-question development set. Not an estimate of overall financial accuracy.",
                questions_sha256=questions_sha256,
            )
            print(f"pilot snapshot written to {PILOT_PATH.name}")
            snapshot_pilot = False

    resources.append({"stage": "end", "working_set_mb": _working_set_mb()})
    summary = _publish(
        OUTPUT_PATH,
        items,
        expected=expected,
        resources=resources,
        note=LABEL if len(items) == expected else (
            f"{LABEL} Partial until status is complete. "
            f"Finished {sum(1 for row in items if row.get('ran'))} of {expected}."
        ),
        questions_sha256=questions_sha256,
    )
    for path_key, digest in protected.items():
        if _sha256(Path(path_key)) != digest:
            raise RuntimeError(f"protected file changed: {path_key}")
    finished = sum(1 for item in items if item.get("ran"))
    if summary.get("status") == "complete":
        print(
            f"validation_150: {summary['correct']} / {summary['total']} "
            f"({summary['accuracy']:.1%})"
        )
        return 0
    print(f"validation_150: {summary['status']}. Finished {finished} of {expected}.")
    return 0


if __name__ == "__main__":
    limit = None
    snapshot = False
    args = sys.argv[1:]
    if "--snapshot-pilot" in args:
        snapshot = True
        args.remove("--snapshot-pilot")
    if "--max-new" in args:
        position = args.index("--max-new")
        limit = int(args[position + 1])
        del args[position:position + 2]
    if args:
        chosen = Path(args[0])
        if not chosen.is_absolute():
            chosen = PROJECT_ROOT / chosen
        globals()["OUTPUT_PATH"] = chosen
    raise SystemExit(main(max_new=limit, snapshot_pilot=snapshot))
