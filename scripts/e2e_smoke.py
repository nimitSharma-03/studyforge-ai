"""Browser end-to-end check of the main StudyForge workflow.

Drives a real Chromium browser through: landing page -> app -> load demo notes -> learning
guide -> ask a question -> mid-semester quiz -> submit -> results -> progress -> question bank,
and saves a screenshot of each step (plus failure.png if a step fails). Works against a local
or deployed frontend.

Usage:
    pip install playwright==1.49.1 && python -m playwright install chromium
    python scripts/e2e_smoke.py http://localhost:4173 [screenshot_dir]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

TIMEOUT_MS = 120_000  # free-tier backends can take about a minute to wake up


def run_workflow(page: Page, base: str, shot) -> None:
    page.goto(base + "/")
    expect(page.get_by_role("heading", level=1)).to_contain_text("From notes to knowledge")
    shot("01-landing")

    page.get_by_role("link", name="Start studying").click()
    expect(page).to_have_url(re.compile(r"/app$"))
    page.get_by_role("button", name="Try the demo notes").first.click()
    expect(page.get_by_text("Topics found")).to_be_visible()
    shot("02-document-summary")

    page.get_by_role("link", name="Start learning").click()
    expect(page.get_by_role("heading", name="Overview")).to_be_visible()
    shot("03-learning-guide")
    page.get_by_role("radio", name="Detailed study").click()
    expect(page.get_by_role("heading", name="Main concepts")).to_be_visible()

    page.get_by_role("tab", name="Ask your notes").click()
    page.get_by_label("Ask a question about your material").fill("Why can accuracy be misleading on imbalanced datasets?")
    page.get_by_role("button", name="Ask", exact=True).click()
    expect(page.get_by_text("Answer from your notes")).to_be_visible()
    shot("04-ask")

    page.get_by_role("link", name="Practice Tests").first.click()
    page.get_by_role("button", name="Start test").click()
    counter = page.get_by_text(re.compile(r"Question 1 of \d+"))
    expect(counter).to_be_visible()
    shot("05-quiz")
    total = int(re.search(r"of (\d+)", counter.inner_text()).group(1))
    for i in range(total):
        page.get_by_role("radio").nth(i % 4).click()
        if i < total - 1:
            page.get_by_role("button", name="Next").click()
    page.get_by_role("button", name="Finish").click()
    page.get_by_role("button", name="Submit quiz").click()
    expect(page.get_by_text("Score by topic")).to_be_visible()
    shot("06-results")

    page.get_by_role("link", name="Progress").first.click()
    expect(page.get_by_role("heading", name="Progress & Revision")).to_be_visible()
    shot("07-progress")

    page.get_by_role("link", name="Question Bank").first.click()
    expect(page.get_by_text(re.compile(r"Showing 1–\d+ of \d+"))).to_be_visible()
    shot("08-question-bank")


def main() -> int:
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:4173"
    shots = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e-screenshots")
    shots.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    expect.set_options(timeout=TIMEOUT_MS)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.set_default_timeout(TIMEOUT_MS)
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        def shot(name: str) -> None:
            page.screenshot(path=str(shots / f"{name}.png"), full_page=True)
            print(f"ok  {name}")

        try:
            run_workflow(page, base, shot)
        except Exception:
            page.screenshot(path=str(shots / "failure.png"), full_page=True)
            print(f"FAILED at {page.url}; screenshot: {shots / 'failure.png'}")
            raise

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto(base + "/")
        mobile.screenshot(path=str(shots / "09-mobile-landing.png"))
        print("ok  09-mobile-landing")
        browser.close()

    relevant = [e for e in console_errors if "favicon" not in e]
    if relevant:
        print("console errors:", *relevant, sep="\n  ")
        return 1
    print("all steps passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
