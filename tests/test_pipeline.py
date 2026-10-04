"""Verify module boundaries without API calls or model downloads."""
import json
from unittest.mock import Mock

import config
from src import pipeline
from src.m2_search import SearchResult
from src.m3_rerank import RerankResult
from src.m4_eval import EvalResult


def test_query_reranks_original_children_and_returns_unique_parents(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    search = Mock()
    search.parent_chunks = {"p1": "Full parent context"}
    search.query_timings = []
    meta = {"parent_id": "p1", "original_text": "Original child"}
    search.search.return_value = [SearchResult("Enriched child", .9, meta, "hybrid")]
    reranker = Mock()
    reranker.rerank.return_value = [RerankResult("Original child", .9, .8, meta, 0)] * 2
    answer, contexts = pipeline.run_query("question", search, reranker)
    assert reranker.rerank.call_args.args[1][0]["text"] == "Original child"
    assert contexts == ["Full parent context"]
    assert answer == contexts[0]
    assert len(search.query_timings) == 1


def test_evaluation_writes_answers_metrics_and_latency(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(pipeline, "load_test_set", lambda: [{"question": "Q", "ground_truth": "GT"}])
    monkeypatch.setattr(pipeline, "run_query", lambda *args: ("A", ["C"]))
    row = EvalResult("Q", "A", ["C"], "GT", .8, .9, .7, .6)
    monkeypatch.setattr(pipeline, "evaluate_ragas", lambda *args: {
        "faithfulness": .8, "answer_relevancy": .9, "context_precision": .7,
        "context_recall": .6, "per_question": [row]})
    search = Mock(timings={}, query_timings=[])
    pipeline.evaluate_pipeline(search, Mock())
    report = json.loads((tmp_path / "reports/ragas_report.json").read_text())
    assert report["per_question"][0]["question"] == "Q"
    assert report["aggregate"]["evaluation_status"] == "completed"
    assert report["failures"][0]["worst_metric"] == "context_recall"
    assert json.loads((tmp_path / "reports/pipeline_answers.json").read_text())[0]["contexts"] == ["C"]
    assert "evaluation_seconds" in json.loads((tmp_path / "reports/latency_report.json").read_text())["build_and_eval"]
