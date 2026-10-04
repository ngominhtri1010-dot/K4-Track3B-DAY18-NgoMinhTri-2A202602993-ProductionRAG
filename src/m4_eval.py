from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json
import math
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from dataclasses import dataclass, asdict, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TEST_SET_PATH


_METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


def _metric_score(value) -> float:
    """Treat missing/failed metric values as zero, keeping reports JSON-safe."""
    if value is None:
        return 0.0
    score = float(value)
    return score if math.isfinite(score) else 0.0


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    unavailable_metrics: list[str] = field(default_factory=list)


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation."""
    # 1. Wrap trong try/except — RAGAS cần OPENAI_API_KEY và Python 3.11+.
    # try:
    #     from ragas import evaluate
    #     from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    #     from datasets import Dataset
    #
    #     dataset = Dataset.from_dict({
    #         "question": questions, "answer": answers,
    #         "contexts": contexts, "ground_truth": ground_truths,
    #     })
    #     result = evaluate(dataset, metrics=[faithfulness, answer_relevancy,
    #                                         context_precision, context_recall])
    #     df = result.to_pandas()
    #     per_question = [EvalResult(question=row["question"], answer=row["answer"],
    #         contexts=row["contexts"], ground_truth=row["ground_truth"],
    #         faithfulness=float(row.get("faithfulness", 0.0)),
    #         answer_relevancy=float(row.get("answer_relevancy", 0.0)),
    #         context_precision=float(row.get("context_precision", 0.0)),
    #         context_recall=float(row.get("context_recall", 0.0)))
    #         for _, row in df.iterrows()]
    #     return {"faithfulness": ..., "answer_relevancy": ...,
    #             "context_precision": ..., "context_recall": ..., "per_question": [...]}
    # except Exception as e:
    #     print(f"  ⚠️  RAGAS evaluation failed: {e}")
    #     return zeros
    if len({len(questions), len(answers), len(contexts), len(ground_truths)}) != 1:
        raise ValueError("questions, answers, contexts and ground_truths must have equal lengths")
    zeros = {**dict.fromkeys(_METRICS, 0.0), "per_question": []}
    if not questions:
        return zeros
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        from datasets import Dataset
        from ragas.run_config import RunConfig
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from config import OPENAI_API_KEY, LLM_BASE_URL, RAGAS_MODEL, RAGAS_EMBEDDING_MODEL

        if not OPENAI_API_KEY:
            raise ValueError("Missing API key for the selected LLM provider")
        llm = ChatOpenAI(model=RAGAS_MODEL, api_key=OPENAI_API_KEY,
                         base_url=LLM_BASE_URL, temperature=0, timeout=60, max_retries=0,
                         max_tokens=2048)
        embeddings = OpenAIEmbeddings(model=RAGAS_EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY, base_url=LLM_BASE_URL,
            check_embedding_ctx_length=False, max_retries=0, request_timeout=60)

        dataset = Dataset.from_dict({
            "question": questions, "answer": answers,
            "contexts": contexts, "ground_truth": ground_truths,
        })
        result = evaluate(dataset, metrics=[faithfulness, answer_relevancy,
                                            context_precision, context_recall],
                          llm=llm, embeddings=embeddings,
                          run_config=RunConfig(max_workers=2, timeout=90, max_retries=2))
        df = result.to_pandas()
        if len(df) != len(questions):
            raise ValueError("RAGAS returned an unexpected number of question results")
        per_question = [EvalResult(
            question=row["question"], answer=row["answer"],
            contexts=list(row["contexts"]), ground_truth=row["ground_truth"],
            unavailable_metrics=[metric for metric in _METRICS
                                 if row.get(metric) is None or not math.isfinite(float(row[metric]))],
            **{metric: _metric_score(row.get(metric, 0.0)) for metric in _METRICS})
            for _, row in df.iterrows()]
        if any(not math.isfinite(float(value))
               for metric in _METRICS for value in df.get(metric, []) if value is not None):
            print("  ⚠️  RAGAS returned non-finite scores; treating failed metrics as 0.0.")
        valid_scores = sum(value is not None and math.isfinite(float(value))
                           for metric in _METRICS for value in df.get(metric, []))
        total_scores = len(questions) * len(_METRICS)
        status = ("completed" if valid_scores == total_scores
                  else "partial" if valid_scores else "unavailable")
        return {**{metric: sum(getattr(row, metric) for row in per_question) / len(per_question)
                   for metric in _METRICS}, "per_question": per_question,
                "evaluation_status": status, "valid_metric_scores": valid_scores}
    except Exception as e:
        print(f"  ⚠️  RAGAS evaluation failed: {e}")
        return zeros


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    # 1. diagnostic_tree = {
    #        "faithfulness": ("LLM hallucinating", "Tighten prompt, lower temperature"),
    #        "context_recall": ("Missing relevant chunks", "Improve chunking or add BM25"),
    #        "context_precision": ("Too many irrelevant chunks", "Add reranking or metadata filter"),
    #        "answer_relevancy": ("Answer doesn't match question", "Improve prompt template"),
    #    }
    # 2. For each EvalResult: compute avg of 4 metrics, find worst_metric
    # 3. Sort by avg ascending → take bottom_n
    # 4. Return [{"question": ..., "worst_metric": ..., "score": ...,
    #             "diagnosis": ..., "suggested_fix": ...}]
    if bottom_n <= 0:
        return []
    diagnostic_tree = {
        "faithfulness": ("LLM hallucinating", "Tighten prompt, lower temperature"),
        "context_recall": ("Missing relevant chunks", "Improve chunking or add BM25"),
        "context_precision": ("Too many irrelevant chunks", "Add reranking or metadata filter"),
        "answer_relevancy": ("Answer doesn't match question", "Improve prompt template"),
    }
    failures = []
    for result in eval_results:
        scores = {metric: _metric_score(getattr(result, metric)) for metric in _METRICS}
        worst_metric = min(scores, key=scores.get)
        diagnosis, suggested_fix = diagnostic_tree[worst_metric]
        failures.append({"question": result.question, "worst_metric": worst_metric,
                         "score": sum(scores.values()) / len(scores),
                         "diagnosis": diagnosis, "suggested_fix": suggested_fix})
    return sorted(failures, key=lambda failure: failure["score"])[:bottom_n]


def save_report(results: dict, failures: list[dict], path: str = "reports/ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(results.get("per_question", [])),
        "failures": failures,
        "per_question": [asdict(row) if isinstance(row, EvalResult) else row
                         for row in results.get("per_question", [])],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
