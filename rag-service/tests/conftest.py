"""Shared fixtures: a deterministic fake embedder and fake LLM so tests need no model downloads."""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from app.chunking import Chunk
from app.store import InMemoryStore

DIM = 256


class HashEmbedder:
    """Bag-of-words hashed into a fixed vector. Texts sharing words get high cosine similarity."""

    def _vec(self, text: str) -> list[float]:
        v = np.zeros(DIM, dtype=np.float32)
        for w in re.findall(r"[a-z0-9]+", text.lower()):
            if len(w) > 2:
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
        return v.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class FakeLLM:
    name = "fake"

    def __init__(self, reply: str = "A blocked account is required [1].") -> None:
        self.reply = reply
        self.calls = 0

    def generate(self, system: str, user: str) -> str:
        self.calls += 1
        return self.reply


def make_chunk(i: int, source: str, text: str) -> Chunk:
    return Chunk(f"id{i}", source, f"Title {source}", f"https://example.org/{source}", i, text)


@pytest.fixture()
def embedder() -> HashEmbedder:
    return HashEmbedder()


@pytest.fixture()
def store(embedder: HashEmbedder) -> InMemoryStore:
    chunks = [
        make_chunk(0, "blocked", "A blocked account Sperrkonto proves financial resources for the student visa."),
        make_chunk(1, "uniassist", "uni-assist checks certificates and transcripts for international applicants."),
        make_chunk(2, "tum", "TUM application period for winter semester ends on 31 May."),
    ]
    s = InMemoryStore()
    s.upsert(chunks, embedder.embed_documents([c.text for c in chunks]))
    return s
