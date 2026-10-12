from fastapi.testclient import TestClient

from app.main import create_app
from app.rag import NO_ANSWER, RagPipeline
from app.store import InMemoryStore
from tests.conftest import FakeLLM, HashEmbedder, make_chunk


def test_retrieval_returns_most_relevant_chunk_first(store: InMemoryStore, embedder: HashEmbedder) -> None:
    hits = store.search(embedder.embed_query("What is a blocked account Sperrkonto?"), k=2)
    assert hits[0].chunk.source_id == "blocked"
    assert hits[0].score > hits[1].score


def test_answer_contains_sources_with_urls(store: InMemoryStore, embedder: HashEmbedder) -> None:
    llm = FakeLLM()
    result = RagPipeline(store, embedder, llm, top_k=2, min_score=0.2).ask("What is a blocked account?")
    assert result.answered and llm.calls == 1
    assert result.sources[0].url == "https://example.org/blocked"


def test_irrelevant_question_says_i_dont_know_without_calling_llm(
    store: InMemoryStore, embedder: HashEmbedder
) -> None:
    llm = FakeLLM()
    result = RagPipeline(store, embedder, llm, top_k=2, min_score=0.2).ask("Best pizza recipe in Naples?")
    assert not result.answered
    assert result.answer == NO_ANSWER
    assert result.sources == []
    assert llm.calls == 0  # the relevance gate must stop the LLM from guessing


def test_llm_refusal_is_passed_through_as_no_answer(store: InMemoryStore, embedder: HashEmbedder) -> None:
    llm = FakeLLM("I don't know.")
    result = RagPipeline(store, embedder, llm, top_k=2, min_score=0.2).ask("blocked account amount?")
    assert not result.answered and result.answer == NO_ANSWER


def test_empty_store_returns_no_answer(embedder: HashEmbedder) -> None:
    result = RagPipeline(InMemoryStore(), embedder, FakeLLM()).ask("anything about Germany")
    assert not result.answered


def test_reingest_replaces_stale_chunks(embedder: HashEmbedder) -> None:
    s = InMemoryStore()
    old = [make_chunk(0, "a", "old text one"), make_chunk(1, "a", "old text two")]
    s.upsert(old, embedder.embed_documents([c.text for c in old]))
    new = [make_chunk(2, "a", "new text only")]
    s.upsert(new, embedder.embed_documents([c.text for c in new]))
    s.upsert(new, embedder.embed_documents([c.text for c in new]))  # idempotent
    assert s.count() == 1


def test_api_ask_and_validation(store: InMemoryStore, embedder: HashEmbedder) -> None:
    pipe = RagPipeline(store, embedder, FakeLLM(), top_k=2, min_score=0.2)
    client = TestClient(create_app(pipe))
    assert client.get("/health").json() == {"status": "ok"}
    ok = client.post("/ask", json={"question": "What is a blocked account?"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["answered"] is True and body["sources"][0]["url"].startswith("https://")
    assert client.post("/ask", json={"question": "x"}).status_code == 422
    assert client.post("/ask", json={}).status_code == 422
