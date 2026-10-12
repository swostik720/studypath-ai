"""The RAG pipeline: retrieve -> relevance gate -> prompt -> LLM -> answer with sources."""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.prompts import ChatPromptTemplate

from app.embeddings import Embedder
from app.llm import LLM
from app.store import Hit, VectorStore

NO_ANSWER = (
    "I don't know. I could not find this in my document collection, so I would rather not guess. "
    "Please check the official source (for example the German embassy, DAAD or the university)."
)

SYSTEM_PROMPT = (
    "You are StudyPath AI, an assistant for students who want to study in Germany. "
    "Answer ONLY with facts stated in the numbered context passages. Do not use outside knowledge. "
    "Cite the passages you used like [1] or [2]. Be concise. "
    "If the context does not contain the answer, reply exactly: I don't know."
)
PROMPT = ChatPromptTemplate.from_messages(
    [("system", SYSTEM_PROMPT), ("human", "Context:\n{context}\n\nQuestion: {question}")]
)


@dataclass
class Source:
    title: str
    url: str
    text: str
    score: float


@dataclass
class Answer:
    answer: str
    sources: list[Source] = field(default_factory=list)
    answered: bool = True  # False when the assistant declined ("I don't know")
    top_score: float = 0.0


def _is_refusal(text: str) -> bool:
    return text.strip().lower().startswith("i don't know") or "i don't know" in text.lower()[:60]


class RagPipeline:
    def __init__(
        self, store: VectorStore, embedder: Embedder, llm: LLM, top_k: int = 4, min_score: float = 0.30
    ) -> None:
        self.store, self.embedder, self.llm = store, embedder, llm
        self.top_k, self.min_score = top_k, min_score

    def retrieve(self, question: str) -> list[Hit]:
        return self.store.search(self.embedder.embed_query(question), self.top_k)

    def ask(self, question: str) -> Answer:
        hits = self.retrieve(question)
        top = hits[0].score if hits else 0.0
        sources = [Source(h.chunk.title, h.chunk.url, h.chunk.text, round(h.score, 4)) for h in hits]
        # Relevance gate: if even the best chunk is weakly related, do not call the LLM at all.
        if not hits or top < self.min_score:
            return Answer(NO_ANSWER, sources=[], answered=False, top_score=top)
        context = "\n\n".join(f"[{i}] ({h.chunk.title}) {h.chunk.text}" for i, h in enumerate(hits, 1))
        messages = PROMPT.format_messages(context=context, question=question)
        text = self.llm.generate(messages[0].content, messages[1].content)
        if _is_refusal(text):
            return Answer(NO_ANSWER, sources=[], answered=False, top_score=top)
        return Answer(text, sources=sources, answered=True, top_score=top)
