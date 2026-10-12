"""Evaluate retrieval and (optionally) answers on eval/questions.json.

Run from rag-service/:
  python -m eval.run_eval                       # retrieval only, no LLM needed
  python -m eval.run_eval --llm hf              # + answers from a local Hugging Face model
  python -m eval.run_eval --llm ollama          # + answers from a local Ollama model

Retrieval uses the in-memory store with the same embedding model and chunking as production
(the pgvector store uses the same cosine metric), so no database is required.
Writes eval/results_<mode>.json.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.chunking import build_chunks
from app.config import get_settings
from app.embeddings import get_embedder
from app.rag import RagPipeline
from app.store import InMemoryStore

HERE = Path(__file__).resolve().parent
THRESHOLDS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]


def key_facts_ok(answer: str, key_facts: list[list[str]]) -> bool:
    """Every group must be matched by at least one of its alternatives (case-insensitive)."""
    low = answer.lower()
    return all(any(alt.lower() in low for alt in group) for group in key_facts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", choices=["none", "hf", "ollama"], default="none")
    parser.add_argument("--min-score", type=float, default=None)
    args = parser.parse_args()

    s = get_settings()
    min_score = s.min_score if args.min_score is None else args.min_score
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    chunks = build_chunks(s.corpus_dir, s.chunk_size, s.chunk_overlap)
    embedder = get_embedder(s.embedding_model)
    store = InMemoryStore()
    store.upsert(chunks, embedder.embed_documents([c.text for c in chunks]))
    print(f"{len(chunks)} chunks from {len({c.source_id for c in chunks})} documents")

    # ---- retrieval
    rows = []
    for q in questions:
        hits = store.search(embedder.embed_query(q["question"]), s.top_k)
        ranked_sources = [h.chunk.source_id for h in hits]
        rank = next((i + 1 for i, sid in enumerate(ranked_sources) if sid in q["expected_sources"]), None)
        rows.append({"question": q["question"], "answerable": q["answerable"], "top_score": hits[0].score,
                     "rank_of_correct_source": rank, "retrieved": ranked_sources})
    ans = [r for r in rows if r["answerable"]]
    n = len(ans)
    retrieval = {
        "n_answerable": n,
        "hit@1": sum(r["rank_of_correct_source"] == 1 for r in ans) / n,
        "hit@3": sum((r["rank_of_correct_source"] or 99) <= 3 for r in ans) / n,
        f"hit@{s.top_k}": sum(r["rank_of_correct_source"] is not None for r in ans) / n,
        "mrr": sum(1 / r["rank_of_correct_source"] for r in ans if r["rank_of_correct_source"]) / n,
    }
    gate = {
        str(t): {
            "answerable_wrongly_refused": sum(r["top_score"] < t for r in ans),
            "unanswerable_wrongly_passed": sum(r["top_score"] >= t for r in rows if not r["answerable"]),
        }
        for t in THRESHOLDS
    }
    out: dict = {"retrieval": retrieval, "gate_by_threshold": gate, "min_score_used": min_score,
                 "n_chunks": len(chunks), "per_question": rows}
    print(json.dumps(retrieval, indent=2))
    print("gate:", json.dumps(gate))

    # ---- answers
    if args.llm != "none":
        from app.llm import HFLocalLLM, OllamaLLM

        llm = HFLocalLLM(s.hf_model) if args.llm == "hf" else OllamaLLM(s.ollama_base_url, s.ollama_model)
        pipe = RagPipeline(store, embedder, llm, top_k=s.top_k, min_score=min_score)
        answers = []
        for q, row in zip(questions, rows, strict=True):
            t0 = time.time()
            res = pipe.ask(q["question"])
            ok = key_facts_ok(res.answer, q["key_facts"]) if q["answerable"] else not res.answered
            answers.append({"question": q["question"], "answerable": q["answerable"], "answered": res.answered,
                            "answer": res.answer, "auto_correct": bool(ok and (res.answered == q["answerable"])),
                            "seconds": round(time.time() - t0, 1), "top_score": row["top_score"]})
            print(f"[{'OK ' if answers[-1]['auto_correct'] else 'BAD'}] {q['question'][:70]} -> {res.answer[:110]!r}")
        out["llm"] = llm.name
        out["answers"] = answers
        a_ans = [a for a in answers if a["answerable"]]
        a_un = [a for a in answers if not a["answerable"]]
        out["answer_summary"] = {
            "answerable_auto_correct": sum(a["auto_correct"] for a in a_ans),
            "answerable_total": len(a_ans),
            "unanswerable_correctly_refused": sum(not a["answered"] for a in a_un),
            "unanswerable_total": len(a_un),
        }
        print(out["answer_summary"])
    (HERE / f"results_{args.llm}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
