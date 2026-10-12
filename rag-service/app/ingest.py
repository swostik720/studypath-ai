"""Ingestion: load -> split -> embed -> store. Safe to re-run (idempotent).

Run: python -m app.ingest
"""

from __future__ import annotations

from app.chunking import build_chunks
from app.config import Settings, get_settings
from app.embeddings import Embedder, get_embedder
from app.store import PgVectorStore, VectorStore


def ingest(settings: Settings, store: VectorStore, embedder: Embedder) -> int:
    chunks = build_chunks(settings.corpus_dir, settings.chunk_size, settings.chunk_overlap)
    vectors = embedder.embed_documents([c.text for c in chunks])
    store.upsert(chunks, vectors)
    return len(chunks)


def main() -> None:
    settings = get_settings()
    store = PgVectorStore(settings.database_url, settings.embedding_dim)
    n = ingest(settings, store, get_embedder(settings.embedding_model))
    print(f"Ingested {n} chunks; table now holds {store.count()} rows.")


if __name__ == "__main__":
    main()
