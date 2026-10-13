"""Take README screenshots of the running stack (http://localhost:3000) with Playwright + local Chrome.

Run: python scripts/screenshots.py
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
URL = "http://localhost:3000"


def ask(page, text: str) -> None:
    page.get_by_label("Your question").fill(text)
    page.get_by_role("button", name="Ask").click()
    page.get_by_role("group", name="Rate this answer").last.wait_for(timeout=600_000)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(URL)
        page.get_by_text("Ask a question about studying in Germany").wait_for()
        page.screenshot(path=OUT / "01-home.png")

        ask(page, "How early should I apply via uni-assist before the deadline?")
        page.get_by_text("Sources (").first.click()
        page.get_by_role("button", name="Helpful answer", exact=True).last.click()
        page.screenshot(path=OUT / "02-answer-with-sources.png")

        ask(page, "Do I need an APS certificate as a Nepali student?")
        page.screenshot(path=OUT / "03-i-dont-know.png")

        mobile = browser.new_page(viewport={"width": 390, "height": 800})
        mobile.goto(URL)
        mobile.get_by_text("Ask a question about studying in Germany").wait_for()
        mobile.screenshot(path=OUT / "04-mobile.png")
        browser.close()


if __name__ == "__main__":
    main()
