"""Vector stores: PostgreSQL + pgvector (production) and an in-memory store (tests / evaluation)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.chunking import Chunk


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float  # cosine similarity in [-1, 1]; higher is more relevant


class VectorStore(Protocol):
    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...

    def search(self, vector: list[float], k: int) -> list[Hit]: ...

    def count(self) -> int: ...


class InMemoryStore:
    """Brute-force cosine search with numpy. Same interface as PgVectorStore."""

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._vecs: dict[str, np.ndarray] = {}

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        # Drop chunks of the same sources that are no longer present (stale after re-ingest).
        new_sources = {c.source_id for c in chunks}
        keep = {c.chunk_id for c in chunks}
        for cid in [i for i, c in self._chunks.items() if c.source_id in new_sources and i not in keep]:
            del self._chunks[cid], self._vecs[cid]
        for chunk, vec in zip(chunks, vectors, strict=True):
            v = np.asarray(vec, dtype=np.float32)
            self._chunks[chunk.chunk_id] = chunk
            self._vecs[chunk.chunk_id] = v / (np.linalg.norm(v) or 1.0)

    def search(self, vector: list[float], k: int) -> list[Hit]:
        if not self._chunks:
            return []
        q = np.asarray(vector, dtype=np.float32)
        q = q / (np.linalg.norm(q) or 1.0)
        ids = list(self._chunks)
        scores = np.stack([self._vecs[i] for i in ids]) @ q
        order = np.argsort(-scores)[:k]
        return [Hit(self._chunks[ids[i]], float(scores[i])) for i in order]

    def count(self) -> int:
        return len(self._chunks)


class PgVectorStore:
    """PostgreSQL table with a pgvector column and an HNSW cosine index."""

    def __init__(self, database_url: str, dim: int = 384) -> None:
        import psycopg  # imported lazily so unit tests do not need a database driver
        from pgvector.psycopg import register_vector

        self._conn = psycopg.connect(database_url, autocommit=True)
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self._conn)
        self._conn.execute(
            f"""CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                chunk_index INT NOT NULL,
                text TEXT NOT NULL,
                embedding vector({dim}) NOT NULL
            )"""
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS chunks_source_idx ON chunks (source_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks "
            "USING hnsw (embedding vector_cosine_ops)"
        )

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        with self._conn.transaction():
            sources = sorted({c.source_id for c in chunks})
            keep = [c.chunk_id for c in chunks]
            # Remove chunks of re-ingested sources whose text changed (stale ids).
            self._conn.execute(
                "DELETE FROM chunks WHERE source_id = ANY(%s) AND NOT (chunk_id = ANY(%s))",
                (sources, keep),
            )
            for chunk, vec in zip(chunks, vectors, strict=True):
                self._conn.execute(
                    """INSERT INTO chunks (chunk_id, source_id, title, url, chunk_index, text, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (chunk_id) DO UPDATE SET
                         title = EXCLUDED.title, url = EXCLUDED.url, embedding = EXCLUDED.embedding""",
                    (
                        chunk.chunk_id,
                        chunk.source_id,
                        chunk.title,
                        chunk.url,
                        chunk.chunk_index,
                        chunk.text,
                        np.asarray(vec, dtype=np.float32),
                    ),
                )

    def search(self, vector: list[float], k: int) -> list[Hit]:
        rows = self._conn.execute(
            """SELECT chunk_id, source_id, title, url, chunk_index, text,
                      1 - (embedding <=> %s) AS score
               FROM chunks ORDER BY embedding <=> %s LIMIT %s""",
            (np.asarray(vector, dtype=np.float32), np.asarray(vector, dtype=np.float32), k),
        ).fetchall()
        return [Hit(Chunk(*r[:6]), float(r[6])) for r in rows]

    def count(self) -> int:
        row = self._conn.execute("SELECT count(*) FROM chunks").fetchone()
        return int(row[0]) if row else 0
