"""Sequential runner for the independent 150-question holdout.

Indexes only the holdout filings named by the question file. Saves after
every question and skips questions that already finished. Does not call
Finnhub or Yahoo Finance and does not write any earlier result file.
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
QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "holdout_150_questions.json"
SOURCES = PROJECT_ROOT / "evaluation" / "holdout_sources"
OUTPUT_PATH = RESULTS_DIR / "holdout_150_results.json"
PILOT_PATH = RESULTS_DIR / "holdout_150_pilot.json"

for _path in (PROJECT_ROOT, BACKEND_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from evaluation.holdout_150 import INDEX_NAMES, verify_questions  # noqa: E402
from evaluation.local_eval import ollama_reachable  # noqa: E402
from evaluation.scoring import answer_correct, is_abstention, summarize  # noqa: E402

LABEL = (
    "Independent holdout on companies and, where available, fiscal years "
    "that were not used to tune TAO-Fin. Not a guarantee of overall financial accuracy."
)

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
    "validation_150_after_routing.json",
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


def _available_memory_mb() -> float | None:
    try:
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = Status()
        status.dwLength = ctypes.sizeof(Status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return round(status.ullAvailPhys / (1024 * 1024), 1)
    except Exception:
        return None


def _resources(stage: str) -> Dict[str, Any]:
    return {
        "stage": stage,
        "working_set_mb": _working_set_mb(),
        "available_memory_mb": _available_memory_mb(),
    }


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


def _bucket(items: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, int]]:
    summary: Dict[str, Dict[str, int]] = {}
    for item in items:
        if not item.get("ran"):
            continue
        name = str(item.get(key) or "unspecified")
        bucket = summary.setdefault(
            name,
            {
                "ran": 0,
                "correct": 0,
                "incorrect_answer": 0,
                "appropriate_abstention": 0,
                "inappropriate_abstention": 0,
                "unresolved_conflict": 0,
            },
        )
        bucket["ran"] += 1
        if item.get("answer_correct"):
            bucket["correct"] += 1
        elif item.get("unresolved_conflict"):
            bucket["unresolved_conflict"] += 1
        elif item.get("appropriate_abstention"):
            bucket["appropriate_abstention"] += 1
        elif item.get("inappropriate_abstention"):
            bucket["inappropriate_abstention"] += 1
        else:
            bucket["incorrect_answer"] += 1
    return summary


def _subset(items: List[Dict[str, Any]], period: str) -> Dict[str, Any]:
    chosen = [item for item in items if item.get("ran") and item.get("period_group") == period]
    correct = sum(1 for item in chosen if item.get("answer_correct"))
    answered = [item for item in chosen if not item.get("abstained")]
    answered_correct = sum(1 for item in answered if item.get("answer_correct"))
    return {
        "questions": len(chosen),
        "correct": correct,
        "accuracy": round(correct / len(chosen), 4) if chosen else None,
        "answered": len(answered),
        "correct_among_answered": (
            round(answered_correct / len(answered), 4) if answered else None
        ),
    }


def _finished(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    found = {}
    for item in payload.get("items") or []:
        if item.get("ran") is True and item.get("id"):
            found[str(item["id"])] = item
    return found


def _classify(item: Dict[str, Any], question: Dict[str, Any], reason: str) -> None:
    expected_abstain = question.get("expected_answer") == "abstain"
    abstained = bool(item.get("abstained"))
    item["appropriate_abstention"] = bool(expected_abstain and abstained)
    item["inappropriate_abstention"] = bool((not expected_abstain) and abstained)
    conflict = abstained and any(
        needle in reason.lower()
        for needle in ("more than one", "conflict")
    )
    item["unresolved_conflict"] = bool(conflict)
    if conflict:
        item["appropriate_abstention"] = False
        item["inappropriate_abstention"] = False


def _score_one(question: Dict[str, Any], pipeline) -> Dict[str, Any]:
    item = {
        "id": question["id"],
        "question": question["question"],
        "category": question.get("category"),
        "ticker": question.get("ticker"),
        "sector": question.get("sector"),
        "fiscal_year": question.get("fiscal_year"),
        "holdout_group": question.get("holdout_group"),
        "period_group": question.get("period_group"),
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
        item["available_memory_mb"] = _available_memory_mb()
        return item
    prediction = output.get("answer", "")
    details = ((output.get("verification") or {}).get("details") or {})
    reason = str(details.get("reason") or "")
    item["ran"] = True
    item["predicted_answer"] = prediction
    item["abstained"] = is_abstention(prediction)
    item["answer_correct"] = answer_correct(prediction, question)
    item["resolver_reason"] = reason or None
    _classify(item, question, reason)
    item["verifier_confidence"] = (output.get("verification") or {}).get("confidence")
    item["latency_seconds"] = output.get("latency_seconds")
    if item["latency_seconds"] is None:
        item["latency_seconds"] = round(time.perf_counter() - started, 2)
    item["working_set_mb"] = _working_set_mb()
    item["available_memory_mb"] = _available_memory_mb()
    return item


def _publish(
    path: Path,
    items: List[Dict[str, Any]],
    *,
    expected: int,
    resources: List[Dict[str, Any]],
    note: str,
    questions_sha256: str,
) -> Dict[str, Any]:
    finished = [item for item in items if item.get("ran")]
    if len(items) == expected and len(finished) == expected:
        summary = summarize(items, expected_total=expected, label=LABEL)
    else:
        summary = {
            "status": "incomplete",
            "label": LABEL,
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
    summary["categories"] = _bucket(finished, "category")
    summary["periods"] = {
        "unseen_period": _subset(finished, "unseen_period"),
        "seen_period_new_company": _subset(finished, "seen_period_new_company"),
    }
    summary["companies"] = _bucket(finished, "ticker")
    answered = [item for item in finished if not item.get("abstained")]
    summary["answer_coverage"] = round(len(answered) / len(finished), 4) if finished else None
    summary["correct_among_answered"] = (
        round(sum(1 for item in answered if item.get("answer_correct")) / len(answered), 4)
        if answered else None
    )
    summary["appropriate_abstentions"] = sum(1 for item in finished if item.get("appropriate_abstention"))
    summary["inappropriate_abstentions"] = sum(
        1 for item in finished if item.get("inappropriate_abstention")
    )
    summary["unresolved_conflicts"] = sum(1 for item in finished if item.get("unresolved_conflict"))
    summary["incorrect_answers"] = sum(
        1 for item in finished
        if item.get("ran")
        and not item.get("answer_correct")
        and not item.get("abstained")
    )
    summary["note"] = note
    summary["questions_sha256"] = questions_sha256
    _write(path, summary)
    return summary


def _filing_records(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    manifest = json.loads((SOURCES / "manifest.json").read_text(encoding="utf-8"))
    by_html = {row["html"]: row for row in manifest}
    by_text = {row["text"]: row for row in manifest}
    chosen = {}
    for question in questions:
        name = Path(str(question.get("source_file") or "")).name
        meta = by_html.get(name) or by_text.get(name)
        if meta is None:
            continue
        chosen[meta["accession"]] = meta
    records = []
    for meta in chosen.values():
        records.append({
            "ticker": meta["ticker"],
            "form": "10-K",
            "text_path": SOURCES / meta["text"],
            "html_path": SOURCES / meta["html"],
        })
    return records


def _pilot_stable(items: List[Dict[str, Any]]) -> bool:
    pilot = [item for item in items if item.get("id", "").startswith("hold-")][:8]
    return len(pilot) >= 8 and all(item.get("ran") for item in pilot[:8])


def main(max_new: int | None = None, pilot_first: bool = False) -> int:
    os.chdir(BACKEND_DIR)
    if OUTPUT_PATH.name in BLOCKED_OUTPUTS or PILOT_PATH.name in BLOCKED_OUTPUTS:
        print(f"refusing to overwrite a protected results file")
        return 2
    if not QUESTIONS_PATH.exists():
        print("holdout questions file is missing")
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
        print(f"holdout already has {len(done)} finished question(s).")
        return 0
    if pilot_first and not done:
        batch = pending[:8]
        continue_after = pending[8:]
    else:
        batch = pending if not max_new or max_new < 0 else pending[:max_new]
        continue_after = []

    ollama_error = ollama_reachable()
    resources = [_resources("start")]
    if ollama_error:
        print(f"blocked. {ollama_error}")
        return 3

    from app.services.rag_index import build_tao_pipeline

    records = _filing_records(questions)
    if not records:
        print("blocked. No holdout filings are attached to the questions.")
        return 3
    pipeline, _indexed = build_tao_pipeline(filing_records=records)
    resources.append(_resources("index"))
    if pipeline is None:
        print("blocked. Holdout index is empty.")
        return 3
    pipeline.company_index = {
        ticker: INDEX_NAMES[ticker]
        for ticker in INDEX_NAMES
        if any(record["ticker"] == ticker for record in records)
    }
    pipeline.allow_external_fallback = False

    ordered = [question["id"] for question in questions]
    items = [done[question["id"]] for question in questions if question["id"] in done]

    def run_batch(selected: List[Dict[str, Any]], stop_on_failure: bool) -> bool:
        for question in selected:
            item = _score_one(question, pipeline)
            items.append(item)
            items.sort(key=lambda row: ordered.index(row["id"]))
            print(
                f"{item['id']}: ran={item['ran']} correct={item.get('answer_correct')} "
                f"abstained={item.get('abstained')} latency={item.get('latency_seconds')} "
                f"ws_mb={item.get('working_set_mb')} avail_mb={item.get('available_memory_mb')}",
                flush=True,
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
            if not item.get("ran"):
                print(f"stopped. {item['id']} did not finish: {item.get('reason')}")
                return False
            available = item.get("available_memory_mb")
            if available is not None and available < 1500:
                print(f"stopped. Available memory fell to {available} MB.")
                return False
            if stop_on_failure and len(items) >= 8 and not PILOT_PATH.exists():
                pilot_items = items[:8]
                if _pilot_stable(pilot_items):
                    _publish(
                        PILOT_PATH,
                        pilot_items,
                        expected=8,
                        resources=resources,
                        note=(
                            "Eight-question safety pilot of the independent holdout. "
                            "Not the full holdout score and not a guarantee of overall financial accuracy."
                        ),
                        questions_sha256=questions_sha256,
                    )
                    print(f"pilot snapshot written to {PILOT_PATH.name}", flush=True)
        return True

    if not run_batch(batch, stop_on_failure=pilot_first):
        return 3
    if continue_after:
        if not _pilot_stable(items):
            print("pilot was not stable. Full holdout was not started.")
            return 3
        print("pilot stable. Continuing the remaining holdout questions.", flush=True)
        if not run_batch(continue_after, stop_on_failure=False):
            return 3

    resources.append(_resources("end"))
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
            f"holdout: {summary['correct']} / {summary['total']} "
            f"({summary['accuracy']:.1%})"
        )
        print("periods", summary.get("periods"))
        return 0
    print(f"holdout: {summary['status']}. Finished {finished} of {expected}.")
    return 0


if __name__ == "__main__":
    limit = None
    pilot_first = "--pilot-first" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg != "--pilot-first"]
    if "--max-new" in args:
        position = args.index("--max-new")
        limit = int(args[position + 1])
    raise SystemExit(main(max_new=limit, pilot_first=pilot_first))
