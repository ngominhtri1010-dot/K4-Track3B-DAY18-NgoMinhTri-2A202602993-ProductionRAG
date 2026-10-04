from __future__ import annotations

"""Production RAG Pipeline — Ghép toàn bộ M1+M2+M3+M4+M5."""

import os, sys, time
import json
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.m1_chunking import load_documents, chunk_hierarchical
from src.m2_search import HybridSearch
from src.m3_rerank import CrossEncoderReranker
from src.m4_eval import load_test_set, evaluate_ragas, failure_analysis, save_report
from src.m5_enrichment import enrich_chunks
from config import RERANK_TOP_K, LLM_BASE_URL, LLM_MODEL


def build_pipeline():
    """Build production RAG pipeline."""
    print("=" * 60)
    print("PRODUCTION RAG PIPELINE")
    print("=" * 60, flush=True)

    # Step 1: Load & Chunk (M1)
    t0 = time.time()
    print("\n[1/4] Chunking documents...", flush=True)
    docs = load_documents()
    all_chunks = []
    parent_chunks = {}
    timings = {}
    for doc in docs:
        parents, children = chunk_hierarchical(doc["text"], metadata=doc["metadata"])
        parent_chunks.update({p.metadata["parent_id"]: p.text for p in parents})
        for child in children:
            all_chunks.append({"text": child.text, "metadata": {**child.metadata, "parent_id": child.parent_id}})
    print(f"  ✓ {len(all_chunks)} chunks from {len(docs)} documents ({time.time()-t0:.1f}s)", flush=True)
    timings["chunking_seconds"] = time.time() - t0

    # Step 2: Enrichment (M5)
    t0 = time.time()
    print(f"\n[2/4] Enriching {len(all_chunks)} chunks (M5, 1 API call/chunk)...", flush=True)
    enriched = enrich_chunks(all_chunks)
    if enriched:
        all_chunks = [{"text": e.enriched_text,
                       "metadata": {**e.auto_metadata, "original_text": e.original_text}}
                      for e in enriched]
        print(f"  ✓ Enriched {len(enriched)} chunks ({time.time()-t0:.1f}s)", flush=True)
    else:
        print("  No enriched chunks; using raw chunks", flush=True)
    timings["enrichment_seconds"] = time.time() - t0

    # Step 3: Index (M2)
    t0 = time.time()
    print(f"\n[3/4] Indexing {len(all_chunks)} chunks (BM25 + Dense)...", flush=True)
    search = HybridSearch()
    search.parent_chunks = parent_chunks
    search.timings = timings
    search.query_timings = []
    search.index(all_chunks)
    timings["indexing_seconds"] = time.time() - t0
    print(f"  ✓ Indexed ({time.time()-t0:.1f}s)", flush=True)

    # Step 4: Reranker (M3)
    t0 = time.time()
    print("\n[4/4] Loading reranker...", flush=True)
    reranker = CrossEncoderReranker()
    reranker._load_model()
    timings["reranker_loading_seconds"] = time.time() - t0
    print(f"  ✓ Reranker ready ({time.time()-t0:.1f}s)", flush=True)

    return search, reranker


def run_query(query: str, search: HybridSearch, reranker: CrossEncoderReranker) -> tuple[str, list[str]]:
    """Run single query through pipeline."""
    t0 = time.perf_counter()
    results = search.search(query)
    retrieval_seconds = time.perf_counter() - t0
    docs = [{"text": r.metadata.get("original_text", r.text),
             "score": r.score, "metadata": r.metadata} for r in results]
    t0 = time.perf_counter()
    reranked = reranker.rerank(query, docs, top_k=RERANK_TOP_K)
    reranking_seconds = time.perf_counter() - t0
    selected = reranked if reranked else results[:RERANK_TOP_K]
    parents = getattr(search, "parent_chunks", {})
    contexts = []
    for result in selected:
        context = parents.get(result.metadata.get("parent_id"),
                              result.metadata.get("original_text", result.text))
        if context not in contexts:
            contexts.append(context)

    from config import OPENAI_API_KEY
    t0 = time.perf_counter()
    if OPENAI_API_KEY and contexts:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY, base_url=LLM_BASE_URL, timeout=30.0, max_retries=0)
            context_str = "\n\n".join(contexts)
            resp = client.chat.completions.create(model=LLM_MODEL, messages=[
                {"role": "system", "content": "Trả lời CHỈ dựa trên context. Nếu không có → nói 'Không tìm thấy.'"},
                {"role": "user", "content": f"Context:\n{context_str}\n\nCâu hỏi: {query}"},
            ])
            answer = resp.choices[0].message.content or contexts[0]
        except Exception as e:
            print(f"  ⚠️  LLM generation failed: {e}", flush=True)
            answer = contexts[0]
    else:
        answer = contexts[0] if contexts else "Không tìm thấy thông tin."
    if hasattr(search, "query_timings"):
        search.query_timings.append({"question": query, "retrieval_seconds": retrieval_seconds,
                                     "reranking_seconds": reranking_seconds,
                                     "generation_seconds": time.perf_counter() - t0})
    return answer, contexts


def evaluate_pipeline(search: HybridSearch, reranker: CrossEncoderReranker):
    """Run evaluation on test set."""
    test_set = load_test_set()
    print(f"\n[Eval] Running {len(test_set)} queries...", flush=True)
    questions, answers, all_contexts, ground_truths = [], [], [], []

    for i, item in enumerate(test_set):
        answer, contexts = run_query(item["question"], search, reranker)
        questions.append(item["question"])
        answers.append(answer)
        all_contexts.append(contexts)
        ground_truths.append(item["ground_truth"])
        print(f"  [{i+1}/{len(test_set)}] {item['question'][:50]}...", flush=True)

    t0 = time.time()
    print(f"\n[Eval] Running RAGAS (4 metrics × {len(test_set)} questions)...", flush=True)
    results = evaluate_ragas(questions, answers, all_contexts, ground_truths)
    from config import OPENAI_API_KEY
    results.setdefault("evaluation_status", "completed" if results.get("per_question") else "unavailable")
    results["answer_mode"] = "llm_with_extractive_fallback" if OPENAI_API_KEY else "extractive"
    results["num_attempted_questions"] = len(questions)
    if hasattr(search, "timings"):
        search.timings["evaluation_seconds"] = time.time() - t0
    print(f"  ✓ RAGAS done ({time.time()-t0:.1f}s)", flush=True)

    print("\n" + "=" * 60)
    print("PRODUCTION RAG SCORES")
    print("=" * 60)
    for m in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        s = results.get(m, 0)
        print(f"  {'✓' if s >= 0.75 else '✗'} {m}: {s:.4f}")

    valid_results = [row for row in results.get("per_question", [])
                     if not row.unavailable_metrics]
    failures = failure_analysis(valid_results, bottom_n=5)
    save_report(results, failures)
    os.makedirs("reports", exist_ok=True)
    with open("reports/pipeline_answers.json", "w", encoding="utf-8") as f:
        json.dump([{"question": q, "answer": a, "contexts": c, "ground_truth": gt}
                   for q, a, c, gt in zip(questions, answers, all_contexts, ground_truths)],
                  f, ensure_ascii=False, indent=2)
    with open("reports/latency_report.json", "w", encoding="utf-8") as f:
        json.dump({"build_and_eval": getattr(search, "timings", {}),
                   "queries": getattr(search, "query_timings", [])}, f, ensure_ascii=False, indent=2)
    return results


if __name__ == "__main__":
    start = time.time()
    search, reranker = build_pipeline()
    evaluate_pipeline(search, reranker)
    print(f"\nTotal: {time.time() - start:.1f}s")
