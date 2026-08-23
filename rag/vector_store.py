"""Local vector storage backed by FAISS."""

from typing import Any, Dict, List, Sequence

import numpy as np

try:
    import faiss
except ImportError:  # pragma: no cover - exercised only without optional dependency
    faiss = None


class FAISSVectorStore:
    """Small local vector database for document embeddings."""

    def __init__(self, dimension: int):
        if faiss is None:
            raise ImportError("FAISS is required. Install it with: pip install faiss-cpu")
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self.documents: List[Dict[str, Any]] = []

    def add(self, documents: Sequence[Dict[str, Any]], embeddings: Sequence[Sequence[float]]) -> None:
        vectors = np.asarray(embeddings, dtype="float32")
        if vectors.ndim != 2 or vectors.shape[1] != self.dimension:
            raise ValueError(f"Expected embeddings with dimension {self.dimension}")
        self.index.add(vectors)
        self.documents.extend(documents)

    def search(self, embedding: Sequence[float], top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.documents:
            return []
        query = np.asarray([embedding], dtype="float32")
        scores, indices = self.index.search(query, min(top_k, len(self.documents)))
        return [
            {**self.documents[index], "vector_score": float(score)}
            for score, index in zip(scores[0], indices[0])
            if index >= 0
        ]
