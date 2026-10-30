"""Run the 12-question validation set. Manual only.

Writes validation_baseline.json with a percentage only if every item finishes.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.local_eval import main_for


if __name__ == "__main__":
    raise SystemExit(main_for("validation"))
