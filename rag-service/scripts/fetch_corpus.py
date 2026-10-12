"""Download the source pages listed in corpus/sources.json and extract their main text.

Run: python scripts/fetch_corpus.py
Writes corpus/<id>.txt (first lines hold title / url / retrieval date). The extracted text is
committed so ingestion is reproducible even if a page changes later.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
HEADERS = {"User-Agent": "Mozilla/5.0 (StudyPath-AI research project)"}
DROP = ["script", "style", "nav", "footer", "header", "form", "noscript", "svg", "aside", "button"]


def extract(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(DROP):
        tag.decompose()
    root = soup.find("main") or soup.find(id=re.compile("content|main", re.I)) or soup.body or soup
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in root.get_text("\n").splitlines()]
    out: list[str] = []
    for ln in lines:
        if ln and (not out or ln != out[-1]):
            out.append(ln)
    return "\n".join(out)


def main() -> None:
    today = dt.date.today().isoformat()
    for src in json.loads((CORPUS / "sources.json").read_text(encoding="utf-8")):
        resp = requests.get(src["url"], headers=HEADERS, timeout=30)
        resp.raise_for_status()
        text = extract(resp.text)
        header = f"TITLE: {src['title']}\nURL: {src['url']}\nRETRIEVED: {today}\n\n"
        (CORPUS / f"{src['id']}.txt").write_text(header + text, encoding="utf-8")
        print(f"{src['id']:24s} {len(text):7d} chars")


if __name__ == "__main__":
    main()
