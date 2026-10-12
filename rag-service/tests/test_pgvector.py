"""Integration test against a real PostgreSQL + pgvector. Skipped unless TEST_DATABASE_URL is set.

CI runs it against a `pgvector/pgvector:pg16` service container.
"""

import os

import pytest

from tests.conftest import HashEmbedder, make_chunk

DB_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(DB_URL is None, reason="TEST_DATABASE_URL not set")


def test_upsert_search_and_idempotency() -> None:
    from app.store import PgVectorStore

    store = PgVectorStore(DB_URL or "", dim=256)
    store._conn.execute("TRUNCATE chunks")
    emb = HashEmbedder()
    chunks = [
        make_chunk(0, "blocked", "A blocked account Sperrkonto proves financial resources."),
        make_chunk(1, "tum", "TUM application period for winter semester ends on 31 May."),
    ]
    vectors = emb.embed_documents([c.text for c in chunks])
    store.upsert(chunks, vectors)
    store.upsert(chunks, vectors)  # re-running ingestion must not duplicate rows
    assert store.count() == 2

    hits = store.search(emb.embed_query("what is a blocked account"), k=2)
    assert hits[0].chunk.source_id == "blocked"
    assert hits[0].score > hits[1].score

    # A changed chunk for the same source replaces the stale one.
    new = [make_chunk(5, "blocked", "Completely different text about visas.")]
    store.upsert(new, emb.embed_documents([c.text for c in new]))
    assert store.count() == 2
    assert all("Sperrkonto" not in h.chunk.text for h in store.search(emb.embed_query("blocked"), k=5))
