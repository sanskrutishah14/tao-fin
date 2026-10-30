"""
Hybrid retriever: FAISS (semantic) + BM25 (keyword) fused via
Reciprocal Rank Fusion (RRF), with an optional cross-encoder reranking pass.

Pipeline:

    query
      ↓
    FAISS semantic search
      +
    BM25 keyword search
      ↓
    RRF fusion
      ↓
    cross-encoder reranking
      ↓
    top-K evidence
"""

from collections import defaultdict
from typing import Dict, List, Optional

from app.services.bm25_index import BM25Index
from app.services.embeddings import EmbeddingService
from app.services.reranker import Reranker
from app.services.vector_store import FAISSVectorStore


class HybridRetriever:
    """
    Combines FAISS semantic search and BM25 keyword search via RRF,
    then optionally reranks the fused shortlist with a cross-encoder.
    """

    def __init__(
        self,
        vector_store: FAISSVectorStore,
        bm25_index: BM25Index,
        embedding_service: EmbeddingService,
        reranker: Optional[Reranker] = None,
        rrf_k: int = 60,
        dense_weight: float = 2.0,
        bm25_weight: float = 1.0,
    ):
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.embedding_service = embedding_service
        self.reranker = reranker
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight

    def get_narrative_chunks(self) -> List[Dict]:
        """Return indexed filing prose. Table grids stay on get_table_chunks."""

        return [
            document
            for document in self.vector_store.documents
            if document.get("metadata", {}).get("type") == "narrative"
        ]

    def get_table_chunks(self) -> List[Dict]:
        """
        Return every indexed table chunk.

        This is used by metrics_resolver.py for deterministic financial
        lookups and calculations. It intentionally scans the indexed
        tables rather than depending only on the top-K retrieval results.
        """

        return [
            document
            for document in self.vector_store.documents
            if document.get("metadata", {}).get("type") == "table"
        ]

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        faiss_candidates: int = 20,
        bm25_candidates: int = 20,
        use_reranker: bool = True,
        mode: str = "hybrid",
    ) -> List[Dict]:
        """
        Full hybrid retrieval pipeline:

        1. FAISS semantic search
        2. BM25 keyword search
        3. RRF fusion (dense-weighted by default)
        4. Cross-encoder reranking
        5. Return top_k

        mode:
            hybrid  - FAISS + BM25 + RRF (+ optional rerank)
            dense   - FAISS only
            bm25    - BM25 only
        """

        query_embedding = self.embedding_service.embed_query(question)

        faiss_results = self.vector_store.search(
            query_embedding,
            top_k=faiss_candidates,
        )

        if mode == "dense":
            return faiss_results[:top_k]

        bm25_results = self.bm25_index.search(
            question,
            top_k=bm25_candidates,
        )

        if mode == "bm25":
            return bm25_results[:top_k]

        fused = self._rrf_fuse(
            faiss_results,
            bm25_results,
        )

        rerank_pool = fused[:max(top_k * 3, 15)]

        if (
            use_reranker
            and self.reranker is not None
            and rerank_pool
        ):
            return self.reranker.rerank(
                question,
                rerank_pool,
                top_k=top_k,
            )

        return fused[:top_k]

    def _rrf_fuse(
        self,
        faiss_results: List[Dict],
        bm25_results: List[Dict],
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion across FAISS and BM25 results.
        """

        rrf_scores: Dict[int, float] = defaultdict(float)
        lookup: Dict[int, Dict] = {}

        for rank, result in enumerate(faiss_results):
            idx = result["index"]

            rrf_scores[idx] += (
                self.dense_weight / (self.rrf_k + rank + 1)
            )

            lookup[idx] = result["document"]

        for rank, result in enumerate(bm25_results):
            idx = result["index"]

            rrf_scores[idx] += (
                self.bm25_weight / (self.rrf_k + rank + 1)
            )

            lookup[idx] = result["document"]

        sorted_indices = sorted(
            rrf_scores,
            key=rrf_scores.get,
            reverse=True,
        )

        return [
            {
                "score": rrf_scores[idx],
                "index": idx,
                "document": lookup[idx],
            }
            for idx in sorted_indices
        ]