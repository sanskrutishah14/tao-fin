"""Live /api/analyze response shape, using a test double for the pipeline.

This does not change TAO, RAG, the verifier, SEC sync, or market data.
It checks that the route still returns the pipeline payload and the
market snapshot it was given.

Run from the backend directory:

    python tests/test_analyze_schema.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.analyze as analyze_route

results = []


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


class FakePipeline:
    def __init__(self):
        self.snapshot = None

    def run(self, question, market_snapshot=None):
        self.snapshot = market_snapshot
        payload = {
            "answer": "AAPL price is 100",
            "evidence": [{"text_preview": "fixture"}],
            "verification": {
                "checks": {
                    "numerical": True,
                    "evidence": True,
                    "logical": True,
                    "financial_consistency": True,
                },
                "confidence": 0.75,
                "failed_checks": [],
                "details": {},
            },
            "query_analysis": {"task_type": "lookup", "difficulty": "simple"},
            "tao": {
                "reasoning_iterations": 0,
                "retrieval_expansions": 0,
                "verification_calls": 0,
                "compute_saved_pct": 100.0,
            },
            "latency_seconds": 0.01,
        }
        if market_snapshot is not None:
            payload["market_snapshot"] = market_snapshot
        return payload


pipeline = FakePipeline()


def fake_ticker(_question):
    return "AAPL"


def fake_ensure(_request, _ticker):
    return pipeline


def fake_snapshot(ticker):
    return {"source": "finnhub_rest", "symbol": ticker, "price": 100.0}


analyze_route.company_service.find_ticker_in_question = fake_ticker
analyze_route._ensure_pipeline = fake_ensure
analyze_route.build_market_snapshot = fake_snapshot

app = FastAPI()
app.include_router(analyze_route.router)
client = TestClient(app)
response = client.post("/api/analyze", json={"question": "What is AAPL's current share price?"})
body = response.json()

record("analyze status 200", response.status_code == 200, f"status={response.status_code} body={body}")
required = ["answer", "evidence", "verification", "query_analysis", "tao", "latency_seconds", "market_snapshot"]
record(
    "analyze response keeps the live schema",
    response.status_code == 200 and all(key in body for key in required),
    f"keys={sorted(body)}",
)
verification = body.get("verification") or {}
checks = verification.get("checks") or {}
record(
    "verifier confidence is passed through",
    verification.get("confidence") == 0.75
    and set(checks) >= {"numerical", "evidence", "logical", "financial_consistency"},
    f"verification={verification}",
)
snapshot = body.get("market_snapshot") or {}
record(
    "market snapshot source symbol and price are passed through",
    snapshot.get("source") == "finnhub_rest" and snapshot.get("symbol") == "AAPL" and snapshot.get("price") == 100.0,
    f"snapshot={snapshot}",
)
record(
    "route called build_market_snapshot before pipeline.run",
    pipeline.snapshot == snapshot,
)

print()
passed = sum(1 for _, flag, _ in results if flag is True)
failed = sum(1 for _, flag, _ in results if flag is False)
print(f"passed={passed} failed={failed}")
sys.exit(1 if failed else 0)
