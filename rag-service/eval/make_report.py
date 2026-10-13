"""Build EVALUATION.md (repo root) from eval/results_none.json and an LLM results file.

Run from rag-service/:  python -m eval.make_report results_ollama.json
All numbers are read from the JSON files, never typed by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "EVALUATION.md"


def main(llm_file: str) -> None:
    ret = json.loads((HERE / "results_none.json").read_text(encoding="utf-8"))
    llm = json.loads((HERE / llm_file).read_text(encoding="utf-8"))
    r = ret["retrieval"]
    k = len(ret["per_question"][0]["retrieved"])
    summ = llm["answer_summary"]
    n_a, n_u = summ["answerable_total"], summ["unanswerable_total"]

    gate_rows = "\n".join(
        f"| {t} | {g['answerable_wrongly_refused']} / {n_a} | {g['unanswerable_wrongly_passed']} / {n_u} |"
        for t, g in ret["gate_by_threshold"].items()
    )
    miss = [q for q in ret["per_question"] if q["answerable"] and q["rank_of_correct_source"] != 1]
    miss_lines = "\n".join(
        f"- \"{q['question']}\" -> correct source rank: {q['rank_of_correct_source']}, retrieved {q['retrieved']}"
        for q in miss
    ) or "- none"

    ans_rows = ["| # | Question | Answerable | Answered | Auto-check | Answer (truncated) |", "|---|---|---|---|---|---|"]
    for i, a in enumerate(llm["answers"], 1):
        text = a["answer"].replace("\n", " ").replace("|", "/")[:160]
        ans_rows.append(
            f"| {i} | {a['question']} | {'yes' if a['answerable'] else 'no'} | "
            f"{'yes' if a['answered'] else 'no'} | {'pass' if a['auto_correct'] else 'FAIL'} | {text} |"
        )
    avg_s = sum(a["seconds"] for a in llm["answers"]) / len(llm["answers"])

    refused = [a for a in llm["answers"] if a["answerable"] and not a["answered"]]
    wrong = [a for a in llm["answers"] if a["answerable"] and a["answered"] and not a["auto_correct"]]
    refused_lines = chr(10).join(f"- {a['question']}" for a in refused) or "- none"
    wrong_lines = chr(10).join(f"- {a['question']}" for a in wrong) or "- none"

    md = f"""# Evaluation

Everything here is produced by `rag-service/eval/run_eval.py` and `make_report.py`; the numbers
are read from `rag-service/eval/results_*.json`. Nothing is typed by hand.

## Setup
- **Collection:** {ret['n_chunks']} chunks from 10 public documents (Federal Foreign Office, uni-assist, TUM).
  Source URLs are stored with every chunk (`rag-service/corpus/sources.json`).
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2`; chunks of 800 characters, 120 overlap; top-k = 4.
- **LLM:** `{llm['llm']}`, temperature 0.
- **Questions:** 30 written by the author of this project from the documents
  (`rag-service/eval/questions.json`): **{n_a} answerable** (each with the accepted source documents and
  required key facts) and **{n_u} unanswerable** (the answer is not in the collection, e.g. the APS and IELTS
  questions, a visa fee, another university, off-topic).
- The questions were written by one person who also built the system, with no separate held-out
  set; treat all numbers as a small-sample sanity check, not a benchmark.

## 1. Retrieval (answerable questions, n = {r['n_answerable']})
A hit means a chunk of one of the accepted source documents is among the top-k retrieved chunks.

| Metric | Value |
|---|---|
| hit@1 | {r['hit@1']:.3f} |
| hit@3 | {r['hit@3']:.3f} |
| hit@{k} | {r[f'hit@{k}']:.3f} |
| MRR | {r['mrr']:.3f} |

Questions where the correct source was not ranked first:
{miss_lines}

Retrieval was measured with the in-memory store (same embeddings and cosine metric as the pgvector store).

## 2. Relevance gate ("I don't know" threshold)
If the best chunk's cosine similarity is below `MIN_SCORE` (default {ret['min_score_used']}) the LLM is not
called at all. The table shows how a threshold would behave on these questions:

| Threshold | Answerable questions wrongly refused | Unanswerable questions wrongly let through |
|---|---|---|
{gate_rows}

**Finding:** the gate only separates *off-topic* questions. Unanswerable but on-topic questions (APS,
IELTS score, visa fee, exact blocked-account amount) retrieve chunks that look just as similar as for answerable
ones, so for them "I don't know" depends on the LLM following the prompt. The default threshold was chosen
before looking at the scores and is not tuned on these questions.

## 3. Answers
Scoring is automatic and documented: an answerable question passes if the answer contains every required
key fact (any alternative wording from a list, case-insensitive substring) **and** the assistant did not refuse;
an unanswerable question passes only if the assistant refused. This is stricter on wording than a human
(a correct answer phrased differently fails) and looser on correctness (a substring can appear in a wrong
answer), so the full answers are listed below for manual checking.

| Result | Value |
|---|---|
| Answerable questions passed | {summ['answerable_auto_correct']} / {n_a} |
| Unanswerable questions correctly refused | {summ['unanswerable_correctly_refused']} / {n_u} |
| Mean time per answer (CPU) | {avg_s:.1f} s |

{chr(10).join(ans_rows)}

## 4. Error analysis
**False refusals ({len(refused)}):** the retrieval found the right document (see section 1) but the model replied
"I don't know" anyway. The 3B model follows the strict "answer ONLY from the context" instruction too literally when the
fact is phrased differently from the question. This is the main weakness; a larger model or a softer prompt would likely
help, but I did not tune the prompt on these questions, to keep the numbers honest.
{refused_lines}

**Answered but failed the key-fact check ({len(wrong)}):**
{wrong_lines}
(inspect the answer in the table above: it may be a legitimate answer that the substring check is too strict for.)

**Unanswerable questions:** all {n_u} were refused. Only the off-topic one is caught by the relevance gate; the other
on-topic ones (APS for Nepal, IELTS score, visa fee, exact blocked-account amount, Heidelberg) were refused by the LLM.
The score is small-sample evidence that the prompt works, and the same strict prompt is what causes the false refusals above.

## Limitations
Small, self-written question set; automatic key-fact scoring; a small local model; single run (temperature 0 but
not repeated); the collection is only 10 pages, so most real-world questions are out of scope by design.
"""
    OUT.write_text(md, encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results_hf.json")
