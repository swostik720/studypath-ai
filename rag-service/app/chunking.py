"""Load corpus text files and split them into chunks (LangChain text splitter)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # stable hash: same text from same source -> same id (makes ingestion idempotent)
    source_id: str
    title: str
    url: str
    chunk_index: int
    text: str


def load_documents(corpus_dir: Path) -> list[dict[str, str]]:
    """Read corpus/sources.json and the matching <id>.txt files (body without the 3-line header)."""
    sources = json.loads((corpus_dir / "sources.json").read_text(encoding="utf-8"))
    docs = []
    for src in sources:
        path = corpus_dir / f"{src['id']}.txt"
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8")
        body = raw.split("\n\n", 1)[1] if raw.startswith("TITLE:") else raw
        docs.append({"id": src["id"], "title": src["title"], "url": src["url"], "text": body})
    return docs


def split_document(
    doc: dict[str, str], chunk_size: int = 800, chunk_overlap: int = 120
) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = []
    for i, text in enumerate(splitter.split_text(doc["text"])):
        digest = hashlib.sha256(f"{doc['id']}|{i}|{text}".encode()).hexdigest()[:32]
        chunks.append(Chunk(digest, doc["id"], doc["title"], doc["url"], i, text))
    return chunks


def build_chunks(corpus_dir: Path, chunk_size: int = 800, chunk_overlap: int = 120) -> list[Chunk]:
    return [
        c
        for doc in load_documents(corpus_dir)
        for c in split_document(doc, chunk_size, chunk_overlap)
    ]
