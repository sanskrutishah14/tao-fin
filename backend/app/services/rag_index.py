"""
Build the in-process RAG index + TAO pipeline from synced SEC filings.

Extracted from main.py so /api/analyze can rebuild the index after an
on-demand company sync, instead of requiring a manual sync + restart.

A first call builds the full index. Later tickers append new filing
chunks and embed only those — existing vectors stay in FAISS.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.db.database import SessionLocal
from app.db.models import Company, SECFiling
from app.services.bm25_index import BM25Index
from app.services.chunker import split_into_chunks
from app.services.embeddings import EmbeddingService
from app.services.hybrid_retriever import HybridRetriever
from app.services.ollama_client import OllamaClient
from app.services.rag_pipeline import RAGPipeline
from app.services.reranker import Reranker
from app.services.table_parser import extract_table_chunks
from app.services.tao_pipeline import TAOPipeline
from app.services.vector_store import FAISSVectorStore


def load_filing_records() -> List[Dict]:
    db = SessionLocal()
    try:
        filings = (
            db.query(SECFiling)
            .filter(SECFiling.local_text_path.isnot(None))
            .all()
        )
        return [
            {
                "text_path": Path(f.local_text_path),
                "html_path": Path(f.local_html_path) if f.local_html_path else None,
                "ticker": f.company.ticker,
                "form": f.form,
            }
            for f in filings
        ]
    finally:
        db.close()


def load_company_index() -> Dict[str, str]:
    db = SessionLocal()
    try:
        return {
            c.ticker: (c.name or c.ticker)
            for c in db.query(Company).all()
        }
    finally:
        db.close()


def filing_key(record: Dict) -> str:
    return f"{record['ticker']}|{record['form']}|{record['text_path'].name}"


def chunks_from_record(record: Dict) -> List[Dict]:
    if not record["text_path"].exists():
        print(f"[index] Skipping missing file: {record['text_path']}")
        return []

    text = record["text_path"].read_text(encoding="utf-8")
    chunks = split_into_chunks(
        text=text,
        chunk_size=1200,
        overlap=200,
        metadata={
            "source": "SEC EDGAR",
            "company": record["ticker"],
            "form": record["form"],
            "filing": record["text_path"].name,
            "type": "narrative",
        },
    )

    html_path = record.get("html_path")
    if html_path and html_path.exists():
        table_chunks = extract_table_chunks(
            str(html_path),
            metadata={
                "source": "SEC EDGAR",
                "company": record["ticker"],
                "form": record["form"],
                "filing": record["text_path"].name,
            },
        )
        chunks.extend(table_chunks)
        print(
            f"[index] Extracted {len(table_chunks)} table chunk(s) "
            f"from {html_path.name}"
        )

    return chunks


def indexed_filing_keys(pipeline: TAOPipeline) -> Set[str]:
    keys: Set[str] = set()
    documents = pipeline.rag_pipeline.retriever.vector_store.documents
    for document in documents:
        metadata = document.get("metadata") or {}
        ticker = metadata.get("company")
        form = metadata.get("form")
        filing = metadata.get("filing")
        if ticker and filing:
            keys.add(f"{ticker}|{form}|{filing}")
    return keys


def indexed_tickers_from_pipeline(pipeline: TAOPipeline) -> Set[str]:
    tickers: Set[str] = set()
    documents = pipeline.rag_pipeline.retriever.vector_store.documents
    for document in documents:
        metadata = document.get("metadata") or {}
        ticker = metadata.get("company")
        if ticker:
            tickers.add(ticker)
    return tickers


def _assemble_pipeline(
    vector_store: FAISSVectorStore,
    bm25_index: BM25Index,
    embedding_service: EmbeddingService,
    reranker: Optional[Reranker] = None,
    ollama_client: Optional[OllamaClient] = None,
) -> TAOPipeline:
    retriever = HybridRetriever(
        vector_store=vector_store,
        bm25_index=bm25_index,
        embedding_service=embedding_service,
        reranker=reranker if reranker is not None else Reranker(),
    )
    rag_pipeline = RAGPipeline(
        retriever=retriever,
        ollama_client=ollama_client if ollama_client is not None else OllamaClient(),
    )
    return TAOPipeline(
        rag_pipeline=rag_pipeline,
        company_index=load_company_index(),
    )


def build_tao_pipeline(
    filing_records: Optional[List[Dict]] = None,
    embedding_service: Optional[EmbeddingService] = None,
    reranker: Optional[Reranker] = None,
    ollama_client: Optional[OllamaClient] = None,
) -> Tuple[Optional[TAOPipeline], Set[str]]:
    """
    Index every synced filing and return (pipeline, indexed_tickers).

    Returns (None, set()) when there is nothing to index. Does not
    raise merely because the corpus is empty.
    """

    records = filing_records if filing_records is not None else load_filing_records()

    if not records:
        return None, set()

    print(f"[index] Indexing {len(records)} filing(s) from the database...")

    embedder = embedding_service or EmbeddingService()
    all_chunks: List[Dict] = []

    for record in records:
        all_chunks.extend(chunks_from_record(record))

    if not all_chunks:
        return None, set()

    embeddings = embedder.embed_documents(
        [c["text"] for c in all_chunks]
    )

    vector_store = FAISSVectorStore(dimension=embeddings.shape[1])
    vector_store.add(embeddings, all_chunks)

    bm25_index = BM25Index()
    bm25_index.build(all_chunks)

    pipeline = _assemble_pipeline(
        vector_store=vector_store,
        bm25_index=bm25_index,
        embedding_service=embedder,
        reranker=reranker,
        ollama_client=ollama_client,
    )

    indexed = {record["ticker"] for record in records}
    print(
        f"[index] Indexed {len(all_chunks)} chunks from {len(records)} filing(s) "
        f"(FAISS + BM25, cross-encoder rerank enabled)."
    )
    return pipeline, indexed


def extend_tao_pipeline(
    pipeline: TAOPipeline,
    filing_records: Optional[List[Dict]] = None,
) -> Tuple[TAOPipeline, Set[str]]:
    """
    Embed only filings that are not already in the live index and
    append them to the existing FAISS store. BM25 is rebuilt from the
    combined document list (cheap compared to re-embedding).
    """

    records = filing_records if filing_records is not None else load_filing_records()
    already = indexed_filing_keys(pipeline)
    new_records = [
        record for record in records if filing_key(record) not in already
    ]

    if not new_records:
        pipeline.company_index = load_company_index()
        return pipeline, indexed_tickers_from_pipeline(pipeline)

    print(
        f"[index] Incrementally adding {len(new_records)} filing(s); "
        f"{len(already)} already indexed."
    )

    new_chunks: List[Dict] = []
    for record in new_records:
        new_chunks.extend(chunks_from_record(record))

    retriever = pipeline.rag_pipeline.retriever

    if new_chunks:
        embeddings = retriever.embedding_service.embed_documents(
            [c["text"] for c in new_chunks]
        )
        retriever.vector_store.add(embeddings, new_chunks)
        retriever.bm25_index.build(retriever.vector_store.documents)
        print(
            f"[index] Added {len(new_chunks)} chunk(s) without re-embedding "
            f"the existing corpus ({len(retriever.vector_store.documents)} total)."
        )
    else:
        print("[index] New filings produced no chunks; index unchanged.")

    pipeline.company_index = load_company_index()
    return pipeline, indexed_tickers_from_pipeline(pipeline)
