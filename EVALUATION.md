# Evaluation

Everything here is produced by `rag-service/eval/run_eval.py` and `make_report.py`; the numbers
are read from `rag-service/eval/results_*.json`. Nothing is typed by hand.

## Setup
- **Collection:** 115 chunks from 10 public documents (Federal Foreign Office, uni-assist, TUM).
  Source URLs are stored with every chunk (`rag-service/corpus/sources.json`).
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2`; chunks of 800 characters, 120 overlap; top-k = 4.
- **LLM:** `ollama:qwen2.5:3b`, temperature 0.
- **Questions:** 30 written by the author of this project from the documents
  (`rag-service/eval/questions.json`): **24 answerable** (each with the accepted source documents and
  required key facts) and **6 unanswerable** (the answer is not in the collection, e.g. the APS and IELTS
  questions, a visa fee, another university, off-topic).
- The questions were written by one person who also built the system, with no separate held-out
  set; treat all numbers as a small-sample sanity check, not a benchmark.

## 1. Retrieval (answerable questions, n = 24)
A hit means a chunk of one of the accepted source documents is among the top-k retrieved chunks.

| Metric | Value |
|---|---|
| hit@1 | 0.958 |
| hit@3 | 0.958 |
| hit@4 | 0.958 |
| MRR | 0.958 |

Questions where the correct source was not ranked first:
- "Besides a blocked account, how else can I prove that I can finance my studies for a student visa?" -> correct source rank: None, retrieved ['aa-sperrkonto', 'aa-sperrkonto', 'aa-sperrkonto', 'ua-apply-online']

Retrieval was measured with the in-memory store (same embeddings and cosine metric as the pgvector store).

## 2. Relevance gate ("I don't know" threshold)
If the best chunk's cosine similarity is below `MIN_SCORE` (default 0.3) the LLM is not
called at all. The table shows how a threshold would behave on these questions:

| Threshold | Answerable questions wrongly refused | Unanswerable questions wrongly let through |
|---|---|---|
| 0.2 | 0 / 24 | 5 / 6 |
| 0.25 | 0 / 24 | 5 / 6 |
| 0.3 | 0 / 24 | 5 / 6 |
| 0.35 | 0 / 24 | 5 / 6 |
| 0.4 | 0 / 24 | 5 / 6 |
| 0.45 | 0 / 24 | 5 / 6 |
| 0.5 | 2 / 24 | 4 / 6 |

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
| Answerable questions passed | 18 / 24 |
| Unanswerable questions correctly refused | 6 / 6 |
| Mean time per answer (CPU) | 30.3 s |

| # | Question | Answerable | Answered | Auto-check | Answer (truncated) |
|---|---|---|---|---|---|
| 1 | How long is a blocked account usually opened for? | yes | no | FAIL | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |
| 2 | Who is the account beneficiary of a blocked account? | yes | yes | pass | [1] The account beneficiary of a blocked account is either the mission abroad where you applied for the visa (before the granting and/or use of the visa) or the |
| 3 | How do I close a blocked account if my visa application was rejected? | yes | no | FAIL | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |
| 4 | Do I have to pay bank fees on top of the amount in the blocked account? | yes | no | FAIL | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |
| 5 | Where can I find out how much money has to be paid into the blocked account? | yes | yes | pass | [1] You can find out what amount has to be paid in to the blocked account based on the purpose of your stay on the website of the competent mission abroad or in |
| 6 | Besides a blocked account, how else can I prove that I can finance my studies for a student visa? | yes | no | FAIL | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |
| 7 | Do I need a visa before entering Germany if I want to study for more than 90 days? | yes | yes | pass | Yes, all foreigners staying in Germany for more than 90 days wanting to work or study in Germany need a visa before entering Germany. [1] |
| 8 | Which authority has to approve a student visa application? | yes | yes | pass | The foreigners authority has to approve a student visa application. [1] |
| 9 | How long can it take to get a student visa? | yes | yes | pass | Several weeks, in individual cases even months. Applicants are encouraged to read all the relevant information on the respective German mission's website carefu |
| 10 | How long does my passport need to be valid when I enter Germany? | yes | yes | pass | It needs to be valid at least for another three months when you enter Germany. |
| 11 | What are the steps to apply through uni-assist? | yes | yes | FAIL | Apply in 6 steps - uni-assist 1. Get information in advance 2. Plan your application 3. Apply online through My assist 4. Upload required documents in My assist |
| 12 | How early should I apply via uni-assist before the deadline? | yes | yes | pass | You should apply at least 8 weeks before the application deadline expires if possible. |
| 13 | How long does uni-assist take to deliver the evaluation result? | yes | yes | pass | uni-assist takes 4 to 6 weeks to deliver the evaluation result. |
| 14 | In what file format should I upload my documents to uni-assist? | yes | no | FAIL | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |
| 15 | Do I need to send my documents to uni-assist by post? | yes | yes | pass | No, you do not need to send documents to uni-assist by post. The application via uni-assist is fully digital. Simply upload all of the required documents in you |
| 16 | What should I do if my certificates were not issued in German or English? | yes | yes | pass | If your certificates were not issued in German or English, you should upload an additional certified translation into German or English. |
| 17 | If I apply to several universities through uni-assist, do I have to upload each document multiple times? | yes | yes | pass | No. You can upload each document once only, even if you are applying to multiple universities or for several courses of study. |
| 18 | What does VPD stand for in the uni-assist process? | yes | yes | pass | VPD stands for Preliminary Review Documentation in the uni-assist process. |
| 19 | What must be written at the top of a letter of motivation for uni-assist? | yes | yes | pass | Name your chosen university and the course of study you are applying to visibly and in bold print at the top of your letter of motivation. [1] |
| 20 | What are the application periods for the Data Engineering and Analytics master's at TUM? | yes | yes | pass | [3] Application Period Winter semester: 01.02. – 31.05. Summer semester: 01.10. – 30.11. |
| 21 | How high are the tuition fees for international students in TUM's Data Engineering and Analytics master's? | yes | yes | pass | 6,000 euros per semester. [3] |
| 22 | What is the language of instruction in TUM's Data Engineering and Analytics master's? | yes | yes | pass | English |
| 23 | How many ECTS credits does the TUM Data Engineering and Analytics master's have? | yes | yes | pass | 120 ECTS |
| 24 | How does TUM select applicants for its master's programs? | yes | yes | pass | TUM selects applicants for its master's programs through an aptitude assessment procedure, which includes evaluating grades from the Bachelor’s program and writ |
| 25 | Do I need an APS certificate as a Nepali student? | no | no | pass | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |
| 26 | What IELTS score does TUM require for the Data Engineering and Analytics master's? | no | no | pass | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |
| 27 | What exact amount in euros do I have to deposit in the blocked account this year? | no | no | pass | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |
| 28 | How much does a German student visa application cost? | no | no | pass | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |
| 29 | What are the tuition fees at Heidelberg University? | no | no | pass | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |
| 30 | Who won the 2022 football World Cup? | no | no | pass | I don't know. I could not find this in my document collection, so I would rather not guess. Please check the official source (for example the German embassy, DA |

## 4. Error analysis
**False refusals (5):** the retrieval found the right document (see section 1) but the model replied
"I don't know" anyway. The 3B model follows the strict "answer ONLY from the context" instruction too literally when the
fact is phrased differently from the question. This is the main weakness; a larger model or a softer prompt would likely
help, but I did not tune the prompt on these questions, to keep the numbers honest.
- How long is a blocked account usually opened for?
- How do I close a blocked account if my visa application was rejected?
- Do I have to pay bank fees on top of the amount in the blocked account?
- Besides a blocked account, how else can I prove that I can finance my studies for a student visa?
- In what file format should I upload my documents to uni-assist?

**Answered but failed the key-fact check (1):**
- What are the steps to apply through uni-assist?
(inspect the answer in the table above: it may be a legitimate answer that the substring check is too strict for.)

**Unanswerable questions:** all 6 were refused. Only the off-topic one is caught by the relevance gate; the other
on-topic ones (APS for Nepal, IELTS score, visa fee, exact blocked-account amount, Heidelberg) were refused by the LLM.
The score is small-sample evidence that the prompt works, and the same strict prompt is what causes the false refusals above.

## Limitations
Small, self-written question set; automatic key-fact scoring; a small local model; single run (temperature 0 but
not repeated); the collection is only 10 pages, so most real-world questions are out of scope by design.
