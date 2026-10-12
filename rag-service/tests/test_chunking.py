import json
from pathlib import Path

from app.chunking import build_chunks, load_documents, split_document


def _write_corpus(tmp: Path, text: str) -> Path:
    (tmp / "sources.json").write_text(
        json.dumps([{"id": "d1", "title": "Doc 1", "url": "https://example.org/d1"}]), encoding="utf-8"
    )
    (tmp / "d1.txt").write_text(f"TITLE: Doc 1\nURL: https://example.org/d1\nRETRIEVED: 2026-01-01\n\n{text}", encoding="utf-8")
    return tmp


def test_header_is_stripped_and_metadata_kept(tmp_path: Path) -> None:
    docs = load_documents(_write_corpus(tmp_path, "Body text only."))
    assert docs[0]["text"] == "Body text only."
    assert docs[0]["url"] == "https://example.org/d1"


def test_chunks_respect_size_and_carry_source_url(tmp_path: Path) -> None:
    text = "\n".join(f"Sentence number {i} about studying in Germany." for i in range(80))
    chunks = build_chunks(_write_corpus(tmp_path, text), chunk_size=300, chunk_overlap=50)
    assert len(chunks) > 3
    assert all(len(c.text) <= 300 for c in chunks)
    assert {c.url for c in chunks} == {"https://example.org/d1"}
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_ids_are_stable_and_unique(tmp_path: Path) -> None:
    text = "\n".join(f"Line {i} with some content." for i in range(60))
    corpus = _write_corpus(tmp_path, text)
    first, second = build_chunks(corpus, 200, 30), build_chunks(corpus, 200, 30)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert len({c.chunk_id for c in first}) == len(first)


def test_overlap_repeats_text_between_neighbouring_chunks() -> None:
    doc = {"id": "d", "title": "t", "url": "u", "text": " ".join(f"word{i}" for i in range(200))}
    chunks = split_document(doc, chunk_size=120, chunk_overlap=40)
    assert set(chunks[0].text.split()) & set(chunks[1].text.split())


def test_real_corpus_loads_with_urls() -> None:
    from app.config import get_settings

    chunks = build_chunks(get_settings().corpus_dir)
    assert len(chunks) > 20
    assert all(c.url.startswith("https://") for c in chunks)
