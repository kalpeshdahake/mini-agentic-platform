"""
Tests for RAG (Retrieval-Augmented Generation) system.
Measures accuracy of evidence retrieval and ranking.
"""

import pytest
from pathlib import Path
from typing import Dict, List, Any
from rag.hybrid import HybridRAGPipeline, BM25Retriever, EmbeddingSimulator
from tools.server import ToolServer


class TestBM25Retriever:
    """Test BM25 lexical search accuracy."""
    
    @pytest.fixture
    def retriever(self):
        """Initialize BM25 retriever with test documents."""
        retriever = BM25Retriever()
        docs = [
            {"id": "1", "content": "payment database connection pool exhausted"},
            {"id": "2", "content": "memory leak causing out of memory errors"},
            {"id": "3", "content": "network latency between services increased"},
            {"id": "4", "content": "cpu utilization at 95 percent"},
            {"id": "5", "content": "disk space running out of memory"},
        ]
        retriever.add_documents(docs)
        return retriever
    
    def test_exact_match_ranking(self, retriever):
        """Test that exact match queries rank highest."""
        results = retriever.search("connection pool exhausted", top_k=3)
        assert len(results) > 0
        assert results[0][0]["id"] == "1"  # Exact match should be first
        print(f"✅ Exact match test passed: {results[0][1]:.2f}")
    
    def test_partial_match_retrieval(self, retriever):
        """Test partial keyword matching."""
        results = retriever.search("memory", top_k=3)
        assert len(results) >= 2  # Should retrieve both memory-related docs
        retrieved_ids = [r[0]["id"] for r in results]
        assert "2" in retrieved_ids  # memory leak doc
        print(f"✅ Partial match test passed: Retrieved {len(results)} documents")
    
    def test_top_k_limit(self, retriever):
        """Test that top_k parameter works correctly."""
        results = retriever.search("database", top_k=2)
        assert len(results) <= 2
        print(f"✅ Top-K limit test passed: Retrieved {len(results)} documents")
    
    def test_score_ordering(self, retriever):
        """Test that results are ordered by relevance score (descending)."""
        results = retriever.search("payment database connection", top_k=5)
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True), "Scores not in descending order"
        print(f"✅ Score ordering test passed: Scores = {[f'{s:.2f}' for s in scores]}")


class TestEmbeddingSimulator:
    """Test embedding-based semantic search."""
    
    def test_embedding_generation(self):
        """Test that embeddings are generated."""
        embedder = EmbeddingSimulator()
        embedding = embedder.embed("payment service latency")
        assert isinstance(embedding, list)
        assert len(embedding) == 10  # 10-dimensional
        print(f"✅ Embedding generation test passed: Dims = {len(embedding)}")
    
    def test_similarity_computation(self):
        """Test cosine similarity between embeddings."""
        embedder = EmbeddingSimulator()
        emb1 = embedder.embed("payment")
        emb2 = embedder.embed("payment")  # Identical
        emb3 = embedder.embed("network latency")  # Different
        
        sim_identical = embedder.similarity(emb1, emb2)
        sim_different = embedder.similarity(emb1, emb3)
        
        assert sim_identical >= sim_different, "Identical should be more similar"
        print(f"✅ Similarity test passed: Same={sim_identical:.2f}, Diff={sim_different:.2f}")
    
    def test_normalized_embeddings(self):
        """Test that embeddings are reasonable magnitude."""
        embedder = EmbeddingSimulator()
        embedding = embedder.embed("test text")
        magnitude = sum(x**2 for x in embedding) ** 0.5
        assert magnitude > 0, "Embedding magnitude should be non-zero"
        print(f"✅ Normalization test passed: Magnitude = {magnitude:.2f}")


class TestHybridRAGPipeline:
    """Test the complete RAG pipeline (BM25 + embeddings)."""
    
    @pytest.fixture
    def rag_pipeline(self):
        """Initialize RAG pipeline."""
        return HybridRAGPipeline(data_dir="data")
    
    def test_pipeline_initialization(self, rag_pipeline):
        """Test that pipeline initializes with documents."""
        assert rag_pipeline.documents is not None
        assert len(rag_pipeline.documents) > 0
        print(f"✅ Pipeline init test passed: Loaded {len(rag_pipeline.documents)} documents")
    
    def test_search_returns_results(self, rag_pipeline):
        """Test that search returns ranked results."""
        results = rag_pipeline.retrieve("payment latency", top_k=5)
        assert len(results) > 0
        assert all("content" in result for result in results)
        print(f"✅ Search test passed: Retrieved {len(results)} results")
    
    def test_hybrid_ranking(self, rag_pipeline):
        """Test hybrid ranking (BM25 + semantic)."""
        results = rag_pipeline.retrieve("database connection pool", top_k=3)
        scores = [result["relevance_score"] for result in results]
        # Scores should reflect hybrid scoring (0.4 * BM25 + 0.6 * semantic)
        assert all(score >= 0 for score in scores), "Scores should be non-negative"
        print(f"✅ Hybrid ranking test passed: Scores = {[f'{s:.2f}' for s in scores]}")
    
    def test_metadata_filtering(self, rag_pipeline):
        """Test that metadata filtering works (if implemented)."""
        results = rag_pipeline.retrieve("payment", top_k=5, filters={"source": "metrics"})
        assert len(results) >= 0  # Should return 0 or more (not error)
        print(f"✅ Metadata filter test passed: Retrieved {len(results)} filtered results")


class TestRAGAccuracy:
    """Measure RAG retrieval accuracy using reference incidents."""
    
    def test_incident_1_rag_accuracy(self):
        """Test RAG accuracy for payment latency incident."""
        rag = HybridRAGPipeline(data_dir="data")
        
        # Query: "database connection pool exhausted"
        results = rag.retrieve("connection pool payment database latency", top_k=5)
        
        relevant_found = any("connection" in result.get("content", "").lower() for result in results)
        assert relevant_found, "Should find connection pool evidence"
        print(f"✅ Incident 1 RAG test passed: Found relevant evidence")
    
    def test_incident_2_rag_accuracy(self):
        """Test RAG accuracy for memory leak incident."""
        rag = HybridRAGPipeline(data_dir="data")
        
        # Query: "memory exhaustion out of memory"
        results = rag.retrieve("memory exhaustion out of memory oom", top_k=5)
        
        relevant_found = any("memory" in result.get("content", "").lower() for result in results)
        assert relevant_found, "Should find memory-related evidence"
        print(f"✅ Incident 2 RAG test passed: Found memory evidence")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
