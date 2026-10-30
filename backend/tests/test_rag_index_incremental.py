"""
Incremental live RAG index: a new ticker must add chunks, not
re-embed the whole corpus.

Run from the backend directory:

    python tests/test_rag_index_incremental.py
"""

import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if not (os.getenv("SEC_USER_AGENT") or "").strip():
    os.environ["SEC_USER_AGENT"] = "TAO-Fin index-test contact@example.com"

from app.db.database import init_db
from app.services.rag_index import build_tao_pipeline, extend_tao_pipeline

results = []


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


class FakeEmbeddings:
    def __init__(self):
        self.document_calls = []

    def embed_documents(self, texts):
        self.document_calls.append(list(texts))
        count = len(texts)
        vectors = np.zeros((count, 8), dtype="float32")
        for index in range(count):
            vectors[index, index % 8] = 1.0
        return vectors

    def embed_query(self, query):
        vector = np.zeros(8, dtype="float32")
        vector[0] = 1.0
        return vector


class FakeReranker:
    def rerank(self, question, documents, top_k=5):
        return documents[:top_k]


class FakeOllama:
    pass


def _record(tmpdir: Path, ticker: str, form: str, text: str):
    path = tmpdir / f"{ticker}_{form}.txt"
    path.write_text(text, encoding="utf-8")
    return {
        "text_path": path,
        "html_path": None,
        "ticker": ticker,
        "form": form,
    }


init_db()

with tempfile.TemporaryDirectory() as raw:
    tmpdir = Path(raw)
    first = _record(tmpdir, "AAPL", "10-K", "Apple reported iPhone revenue of 200 billion.")
    second = _record(tmpdir, "MSFT", "10-K", "Microsoft reported Azure revenue of 80 billion.")
    embedder = FakeEmbeddings()

    pipeline, indexed = build_tao_pipeline(
        filing_records=[first],
        embedding_service=embedder,
        reranker=FakeReranker(),
        ollama_client=FakeOllama(),
    )

    record("initial build returns a pipeline", pipeline is not None)
    record("initial index contains AAPL only", indexed == {"AAPL"}, f"indexed={indexed}")
    record(
        "initial embed saw only AAPL chunks",
        len(embedder.document_calls) == 1
        and all("Apple" in text for text in embedder.document_calls[0]),
        f"calls={len(embedder.document_calls)}",
    )

    first_chunk_count = len(pipeline.rag_pipeline.retriever.vector_store.documents)
    record("initial corpus is non-empty", first_chunk_count >= 1, f"n={first_chunk_count}")

    pipeline, indexed = extend_tao_pipeline(
        pipeline,
        filing_records=[first, second],
    )

    record("extend adds MSFT", "MSFT" in indexed and "AAPL" in indexed, f"indexed={indexed}")
    record(
        "extend embeds only the new ticker",
        len(embedder.document_calls) == 2
        and all("Microsoft" in text for text in embedder.document_calls[1]),
        f"calls={len(embedder.document_calls)} last={embedder.document_calls[-1][:1]}",
    )

    total = len(pipeline.rag_pipeline.retriever.vector_store.documents)
    record(
        "extend keeps previous chunks",
        total > first_chunk_count,
        f"before={first_chunk_count} after={total}",
    )

    before_calls = len(embedder.document_calls)
    pipeline, indexed = extend_tao_pipeline(
        pipeline,
        filing_records=[first, second],
    )
    record(
        "second extend is a no-op",
        len(embedder.document_calls) == before_calls,
        f"calls={len(embedder.document_calls)}",
    )

print()
passed = sum(1 for _, flag, _ in results if flag is True)
failed = sum(1 for _, flag, _ in results if flag is False)
print(f"passed={passed} failed={failed}")
sys.exit(1 if failed else 0)
