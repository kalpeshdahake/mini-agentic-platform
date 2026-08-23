"""
Hybrid RAG (Retrieval-Augmented Generation) pipeline.
Implements BM25 lexical search + embedding-based semantic search.
"""

import json
import math
import os
from typing import List, Dict, Any, Tuple
from pathlib import Path
from collections import defaultdict


class BM25Retriever:
    """
    BM25 (Best Matching 25) lexical search implementation.
    Used for fast keyword-based document retrieval.
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1  # Term frequency tuning parameter
        self.b = b    # Length normalization parameter
        self.documents: List[Dict[str, Any]] = []
        self.idf_cache: Dict[str, float] = {}
    
    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents to the retriever."""
        self.documents = documents
        self._compute_idf()
    
    def _compute_idf(self) -> None:
        """Compute IDF (Inverse Document Frequency) for all terms."""
        doc_count = len(self.documents)
        term_doc_count = defaultdict(int)
        
        for doc in self.documents:
            terms = self._tokenize(doc.get("content", ""))
            for term in set(terms):  # Count unique terms per document
                term_doc_count[term] += 1
        
        for term, count in term_doc_count.items():
            # BM25 IDF formula
            self.idf_cache[term] = math.log((doc_count - count + 0.5) / (count + 0.5) + 1)
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization (lowercase, split by whitespace)."""
        return text.lower().split()
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for documents matching the query.
        Returns list of (document, score) tuples sorted by score.
        """
        query_terms = self._tokenize(query)
        scores = []
        
        avg_doc_len = sum(len(self._tokenize(doc.get("content", ""))) for doc in self.documents) / len(self.documents) if self.documents else 1
        
        for doc in self.documents:
            doc_terms = self._tokenize(doc.get("content", ""))
            doc_len = len(doc_terms)
            score = 0.0
            
            for term in query_terms:
                term_count = doc_terms.count(term)
                if term_count > 0:
                    idf = self.idf_cache.get(term, 0)
                    # BM25 formula
                    tf_component = (self.k1 + 1) * term_count / (self.k1 * (1 - self.b + self.b * doc_len / avg_doc_len) + term_count)
                    score += idf * tf_component
            
            if score > 0:
                scores.append((doc, score))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class EmbeddingSimulator:
    """
    Simulated embedding model for semantic search.
    In production, use SentenceTransformers or similar.
    """
    
    def __init__(self):
        """Initialize with simple embedding strategy."""
        pass
    
    def embed(self, text: str) -> List[float]:
        """
        Generate a simple hash-based embedding.
        In production, use real embeddings from sentence-transformers.
        """
        # Simple embedding based on word hashes (for demo only)
        words = text.lower().split()
        embedding = [0.0] * 10  # 10-dimensional embedding
        
        for word in words:
            word_hash = hash(word)
            for i in range(10):
                embedding[i] += math.sin(word_hash + i) * 0.1
        
        # Normalize
        magnitude = math.sqrt(sum(x**2 for x in embedding)) or 1
        return [x / magnitude for x in embedding]
    
    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        dot_product = sum(e1 * e2 for e1, e2 in zip(embedding1, embedding2))
        return dot_product


class SentenceTransformerEmbedder:
    """Open-source local embeddings using all-MiniLM-L6-v2."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> List[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        return max(-1.0, min(1.0, sum(a * b for a, b in zip(embedding1, embedding2))))


class HybridRAGPipeline:
    """
    Hybrid RAG combining BM25 lexical search and semantic search.
    Retrieves relevant documents for agent reasoning.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.bm25 = BM25Retriever()
        self.embedding_model = "hash-simulator"
        try:
            self.embedder = SentenceTransformerEmbedder(
                os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            )
            self.embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        except (ImportError, OSError, RuntimeError):
            self.embedder = EmbeddingSimulator()
        self.documents: List[Dict[str, Any]] = []
        self.vector_store = None
        self._load_documents()
    
    def _load_documents(self) -> None:
        """Load all available documents from data directory."""
        # Load runbooks
        runbooks_dir = self.data_dir / "runbooks"
        if runbooks_dir.exists():
            for runbook_file in runbooks_dir.glob("*.md"):
                with open(runbook_file, 'r') as f:
                    content = f.read()
                    self.documents.append({
                        "id": runbook_file.stem,
                        "type": "runbook",
                        "title": runbook_file.stem.replace("_", " "),
                        "content": content,
                        "path": str(runbook_file),
                    })
        
        # Load infrastructure metadata
        infra_file = self.data_dir / "infrastructure" / "services.json"
        if infra_file.exists():
            with open(infra_file, 'r') as f:
                infra_data = json.load(f)
                self.documents.append({
                    "id": "infrastructure",
                    "type": "metadata",
                    "title": "Infrastructure Configuration",
                    "content": json.dumps(infra_data, indent=2),
                    "path": str(infra_file),
                })
        
        # Initialize BM25 with documents
        self.bm25.add_documents(self.documents)
        
        # Precompute embeddings
        self.document_embeddings = {
            doc["id"]: self.embedder.embed(doc["content"])
            for doc in self.documents
        }

        try:
            from rag.vector_store import FAISSVectorStore

            self.vector_store = FAISSVectorStore(len(next(iter(self.document_embeddings.values()))))
            self.vector_store.add(self.documents, list(self.document_embeddings.values()))
        except (ImportError, ValueError, StopIteration):
            self.vector_store = None
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Dict[str, str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the most relevant documents.
        Combines BM25 and semantic search results.
        """
        # BM25 search
        bm25_results = self.bm25.search(query, top_k=top_k)
        bm25_docs = {doc["id"]: score for doc, score in bm25_results}
        
        # Semantic search
        query_embedding = self.embedder.embed(query)
        if self.vector_store is not None:
            vector_results = self.vector_store.search(query_embedding, top_k=len(self.documents))
            semantic_scores = {
                result["id"]: result["vector_score"]
                for result in vector_results
            }
        else:
            semantic_scores = {}
            for doc in self.documents:
                doc_id = doc["id"]
                doc_embedding = self.document_embeddings.get(doc_id)
                if doc_embedding:
                    score = self.embedder.similarity(query_embedding, doc_embedding)
                    semantic_scores[doc_id] = score
        
        # Combine rankings (normalize and merge)
        combined_scores = {}
        for doc_id in set(list(bm25_docs.keys()) + list(semantic_scores.keys())):
            bm25_score = bm25_docs.get(doc_id, 0)
            semantic_score = semantic_scores.get(doc_id, 0)
            # Weighted combination
            combined_scores[doc_id] = 0.4 * bm25_score + 0.6 * (semantic_score + 0.5)
        
        # Sort and return top-k
        sorted_docs = sorted(
            combined_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        # Build result documents with scores
        results = []
        for doc_id, score in sorted_docs:
            doc = next((d for d in self.documents if d["id"] == doc_id), None)
            if doc:
                results.append({
                    **doc,
                    "relevance_score": score,
                })
        
        # Apply filters if provided
        if filters:
            results = [
                doc for doc in results
                if all(doc.get(k) == v for k, v in filters.items())
            ]
        
        return results
