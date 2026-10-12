"""FastAPI service: POST /ask, GET /health."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.config import get_settings
from app.embeddings import get_embedder
from app.ingest import ingest
from app.llm import get_llm
from app.rag import RagPipeline
from app.store import InMemoryStore, PgVectorStore, VectorStore


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class SourceOut(BaseModel):
    title: str
    url: str
    text: str
    score: float


class AskResponse(BaseModel):
    answer: str
    answered: bool
    sources: list[SourceOut]
    top_score: float


def create_app(pipeline: RagPipeline | None = None) -> FastAPI:
    app = FastAPI(title="StudyPath RAG service")
    state: dict[str, RagPipeline] = {}
    if pipeline is not None:
        state["pipeline"] = pipeline

    def get_pipeline() -> RagPipeline:
        # Built lazily on the first request so /health works even while models are loading.
        if "pipeline" not in state:
            s = get_settings()
            embedder = get_embedder(s.embedding_model)
            store: VectorStore
            if s.vector_store == "memory":
                store = InMemoryStore()
                ingest(s, store, embedder)
            else:
                store = PgVectorStore(s.database_url, s.embedding_dim)
            state["pipeline"] = RagPipeline(
                store,
                embedder,
                get_llm(s),
                top_k=s.top_k,
                min_score=s.min_score,
            )
        return state["pipeline"]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        result = get_pipeline().ask(req.question.strip())
        return AskResponse(
            answer=result.answer,
            answered=result.answered,
            sources=[SourceOut(**asdict(s)) for s in result.sources],
            top_score=round(result.top_score, 4),
        )

    return app


app = create_app()
