"""Settings read from environment variables (see .env.example at the repo root)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get(
        "DATABASE_URL", "postgresql://studypath:studypath@localhost:5432/studypath"
    )
    # "pgvector" (production) or "memory" (no database: indexes the corpus at startup; for local dev)
    vector_store: str = os.environ.get("VECTOR_STORE", "pgvector")
    embedding_model: str = os.environ.get(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    embedding_dim: int = 384  # output size of all-MiniLM-L6-v2; must match the pgvector column
    corpus_dir: Path = Path(os.environ.get("CORPUS_DIR", str(ROOT / "corpus")))
    chunk_size: int = int(os.environ.get("CHUNK_SIZE", "800"))
    chunk_overlap: int = int(os.environ.get("CHUNK_OVERLAP", "120"))
    top_k: int = int(os.environ.get("TOP_K", "4"))
    # Minimum cosine similarity of the best chunk; below it the assistant answers "I don't know".
    min_score: float = float(os.environ.get("MIN_SCORE", "0.30"))
    llm_provider: str = os.environ.get("LLM_PROVIDER", "ollama")  # ollama | hf
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
    hf_model: str = os.environ.get("HF_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")


def get_settings() -> Settings:
    return Settings()
