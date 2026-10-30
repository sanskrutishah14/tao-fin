"""Run the 8-question local smoke test. Manual only."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.local_eval import main_for


if __name__ == "__main__":
    raise SystemExit(main_for("smoke"))
