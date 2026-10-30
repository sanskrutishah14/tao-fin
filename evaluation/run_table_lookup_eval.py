"""Run the 12 validation questions after the table-lookup change.

Does not write evaluation/results/validation_baseline.json.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.local_eval import RESULTS_DIR, run_kind


AFTER_LABEL = (
    "Validation set after deterministic table lookup. "
    "Same 12 questions and gold values as the Phase A baseline. "
    "Not an estimate of overall financial answer accuracy."
)


def main() -> int:
    return run_kind(
        "validation",
        summary_path=RESULTS_DIR / "validation_after_table_lookup.json",
        label=AFTER_LABEL,
    )


if __name__ == "__main__":
    raise SystemExit(main())
