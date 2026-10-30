"""Read-only smoke and validation summaries.

These routes never start Ollama, never score a live answer, and never
invent a percentage. A missing file is not_run. Any status other than
complete has its accuracy field removed before the response is sent.
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter


router = APIRouter(prefix="/api/eval", tags=["Evaluation"])

_LABELS = {
    "smoke": (
        "8-question local smoke test. Not an estimate of overall TAO-Fin accuracy."
    ),
    "validation": (
        "Fixed validation set. Use only for before-and-after comparison. "
        "Not an estimate of overall financial answer accuracy."
    ),
    "dev": (
        "50-question development benchmark run."
    ),
}

_FILES = {
    "smoke": "smoke_summary.json",
    "validation": "validation_baseline.json",
    "dev": "validation_50_baseline.json",
}


def results_dir() -> Path:
    override = os.getenv("TAO_EVAL_RESULTS_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "evaluation" / "results"


def _load_gold_map(kind: str) -> dict:
    eval_dir = Path(__file__).resolve().parents[3] / "evaluation"
    res = {}
    for filename in [f"{kind}_questions.json", "smoke_questions.json", "validation_questions.json", "validation_50_questions.json"]:
        q_file = eval_dir / filename
        if q_file.exists():
            try:
                data = json.loads(q_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for q in data:
                        qid = q.get("id")
                        val = q.get("gold_value")
                        unit = q.get("gold_unit", "")
                        if qid and val is not None and qid not in res:
                            if unit == "percent":
                                fmt = f"{val}%"
                            elif unit in ("million", "millions"):
                                fmt = f"${val:,.0f}M" if isinstance(val, (int, float)) else f"${val}M"
                            elif unit in ("billion", "billions"):
                                fmt = f"${val:,.2f}B" if isinstance(val, (int, float)) else f"${val}B"
                            elif unit == "usd_per_share":
                                fmt = f"${val:,.2f}" if isinstance(val, (int, float)) else f"${val}"
                            else:
                                fmt = f"{val} {unit}".strip()
                            res[qid] = fmt
            except Exception:
                pass
    return res


def read_summary(kind: str) -> dict:
    label = _LABELS.get(kind, f"Benchmark run: {kind}")
    filename = _FILES.get(kind, f"{kind}.json")
    path = results_dir() / filename
    if not path.exists():
        return {"status": "not_run", "label": label}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "blocked",
            "label": label,
            "reason": f"Summary file is not valid JSON: {path.name}",
        }
    if not isinstance(data, dict):
        return {
            "status": "blocked",
            "label": label,
            "reason": f"Summary file is not an object: {path.name}",
        }
    data["label"] = label
    if data.get("status") != "complete":
        data.pop("accuracy", None)
        data.pop("correct", None)
        data.pop("total", None)

    gold_map = _load_gold_map(kind)
    for item in data.get("items", []):
        if not item.get("gold_answer") and item.get("id") in gold_map:
            item["gold_answer"] = gold_map[item["id"]]

    return data


@router.get("/smoke")
def smoke_summary():
    return read_summary("smoke")


@router.get("/validation")
def validation_summary():
    return read_summary("validation")


@router.get("/dev")
def dev_summary():
    return read_summary("dev")


@router.get("/runs")
def list_runs():
    return {
        "runs": [
            {"id": "smoke", "label": "Smoke (8)", "count": 8},
            {"id": "validation", "label": "Validation (12)", "count": 12},
            {"id": "dev", "label": "Dev Run (50)", "count": 50},
        ]
    }
