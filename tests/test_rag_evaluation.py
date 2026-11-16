import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import sqlite3
from evaluation.rag_evaluator import rag_evaluator

def test_rag_production_db_unmodified():
    """Verify evaluation does not mutate or modify the production memory database."""
    db_path = rag_evaluator.memory_db_path
    assert db_path.exists(), f"Production memory.db not found at {db_path}"

    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
        before_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    # Run full evaluation
    report = rag_evaluator.generate_full_evaluation_report()
    assert report is not None

    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
        after_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    assert before_count == after_count, "Evaluation modified production memory database!"
    assert before_count >= 1000

def test_rag_benchmark_retrieval_metrics():
    """Verify precision, recall, hit rate, and negative rejection thresholds."""
    report = rag_evaluator.generate_full_evaluation_report()
    m = report["metrics"]

    assert m["total_queries"] >= 10
    assert m["hit_rate_at_k"] >= 0.80, f"Hit rate {m['hit_rate_at_k']} fell below 80%"
    assert m["mean_reciprocal_rank"] >= 0.70, f"MRR {m['mean_reciprocal_rank']} fell below 0.70"
    assert m["negative_rejection_rate"] >= 0.90, f"Negative rejection {m['negative_rejection_rate']} fell below 90%"
    assert m["average_latency_ms"] < 50.0, f"Average query latency {m['average_latency_ms']}ms exceeded 50ms"

def test_rag_write_and_retrieve_isolated():
    """Verify write-after-read integrity and version handling in isolated sandbox."""
    res = rag_evaluator.test_write_and_retrieve_isolated()
    assert res["ok"] is True
    assert res["write_retrieve_passed"] is True
    assert res["version_update_passed"] is True
    assert res["retrieval_latency_ms"] < 100.0

def test_rag_markdown_report():
    """Verify generated markdown report structure and known limitations."""
    md = rag_evaluator.generate_markdown_report()
    assert "# Operation JARVIS — RAG and Memory Retrieval Evaluation Report" in md
    assert "Hit Rate" in md
    assert "Mean Reciprocal Rank" in md
    assert "Write-Then-Retrieve Verification" in md
    assert "Known Limitations & Technical Constraints" in md
    assert "FTS5 BM25" in md
