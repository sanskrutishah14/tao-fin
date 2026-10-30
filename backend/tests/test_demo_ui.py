"""
Thin demo UI is served at /ui and posts {question} to /api/analyze.

Run from the backend directory:

    python tests/test_demo_ui.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient

results = []


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
html = FRONTEND.read_text(encoding="utf-8") if FRONTEND.exists() else ""

record("frontend/index.html exists", FRONTEND.exists(), str(FRONTEND))
record("UI posts to /api/analyze", "/api/analyze" in html)
record("UI renders verification", "verification" in html)
record("UI renders TAO stats", "reasoning_iterations" in html and "compute_saved_pct" in html)
record("UI renders market snapshot source", "market_snapshot" in html and "source" in html)
record("UI renders evidence", "evidence" in html)
record("UI has a separate smoke card", 'id="smoke-card"' in html and "8-question local smoke test" in html)
record("UI has a separate validation card", 'id="validation-card"' in html and "/api/eval/validation" in html)
record(
    "smoke card is not the verifier confidence pill",
    "verification.confidence" in html and "smoke-card" in html and html.index("smoke-card") < html.index("confidence"),
)

app = FastAPI()


@app.get("/ui")
def demo_ui():
    return FileResponse(FRONTEND)


client = TestClient(app)
response = client.get("/ui")
record(
    "/ui serves the demo page",
    response.status_code == 200 and "TAO-Fin" in response.text,
    f"status={response.status_code} type={response.headers.get('content-type')}",
)

print()
passed = sum(1 for _, flag, _ in results if flag is True)
failed = sum(1 for _, flag, _ in results if flag is False)
print(f"passed={passed} failed={failed}")
sys.exit(1 if failed else 0)
