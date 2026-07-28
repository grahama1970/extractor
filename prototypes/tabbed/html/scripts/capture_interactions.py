#!/usr/bin/env python3
"""
Capture comprehensive interaction screenshots for /review-design.
Uses Playwright with mock data mode (?mock=true).

Captures:
1. Static views (all 3 surfaces populated)
2. Interaction states (selection, hover, expanded, filter)
3. HUD mode (NVIS compliance)
4. Component details (zoom, search, bbox editor)
"""
import os
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Installing playwright...")
    os.system(f"{sys.executable} -m pip install playwright && playwright install chromium")
    from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8080"
MOCK = "?mock=true"
OUT = Path(__file__).parent.parent.parent.parent.parent / "pi-mono/.pi/skills/review-pdf/design/figures/interactions"
OUT.mkdir(parents=True, exist_ok=True)

def capture(page, name, url=None, wait_ms=800, actions=None, full_page=False):
    """Navigate (if url given), run actions, screenshot."""
    if url:
        page.goto(f"{BASE_URL}{url}{MOCK}", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(wait_ms)
    if actions:
        actions(page)
        page.wait_for_timeout(400)
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=full_page)
    print(f"  [{name}]")
    return path


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1919, "height": 1080},
            device_scale_factor=2,
            color_scheme="dark",
        )
        page = ctx.new_page()

        print("=== Surface 1: ReviewLayout ===")

        # 1a. Review — populated run list
        capture(page, "review-01-populated", "/review")

        # 1b. Review — select first run in sidebar
        def click_first_run(p):
            buttons = p.query_selector_all("button.w-full.text-left")
            if buttons:
                buttons[0].click()
                p.wait_for_timeout(1000)
        capture(page, "review-02-run-selected", actions=click_first_run)

        # 1c. Review — scores panel visible (click second run for variety)
        def click_second_run(p):
            buttons = p.query_selector_all("button.w-full.text-left")
            if len(buttons) > 1:
                buttons[1].click()
                p.wait_for_timeout(1000)
        capture(page, "review-03-scores-panel", actions=click_second_run)

        # 1d. Review — search filter
        def type_search(p):
            search = p.query_selector('input[placeholder*="Search"]') or p.query_selector('input[placeholder*="search"]') or p.query_selector('input[type="text"]')
            if search:
                search.fill("NIST")
                p.wait_for_timeout(500)
        capture(page, "review-04-search-filter", "/review", actions=type_search)

        print("\n=== Surface 2: QuarantineView ===")

        # 2a. Quarantine — populated verdicts dashboard
        capture(page, "quarantine-01-populated", "/quarantine")

        # 2b. Quarantine — with search filter
        def quarantine_search(p):
            search = p.query_selector('input[placeholder*="Search"]') or p.query_selector('input[placeholder*="search"]') or p.query_selector('input[type="text"]')
            if search:
                search.fill("MIL")
                p.wait_for_timeout(300)
        capture(page, "quarantine-02-search", actions=quarantine_search)

        # 2c. Quarantine — click a row to expand scores
        def expand_scores(p):
            # Click a table row to expand
            rows = p.query_selector_all("tr, [role=row]")
            clickable = [r for r in rows if "cursor" in (r.get_attribute("class") or "")]
            if clickable:
                clickable[0].click()
                p.wait_for_timeout(500)
            else:
                # Try clicking stem text
                stems = p.query_selector_all(".font-mono")
                if stems:
                    stems[0].click()
                    p.wait_for_timeout(500)
        capture(page, "quarantine-03-expanded-scores", "/quarantine", actions=expand_scores)

        # 2d. Quarantine — FAIL filter only
        def filter_fail(p):
            # Look for a FAIL badge/button to click
            fail_btns = p.query_selector_all("text=FAIL")
            if fail_btns:
                fail_btns[0].click()
                p.wait_for_timeout(500)
        capture(page, "quarantine-04-fail-filter", actions=filter_fail)

        # 2e. Quarantine — select multiple items (checkbox selection)
        def select_multiple(p):
            checkboxes = p.query_selector_all('input[type="checkbox"], [role="checkbox"]')
            for cb in checkboxes[:3]:
                cb.click()
                p.wait_for_timeout(100)
        capture(page, "quarantine-05-multi-select", "/quarantine", actions=select_multiple)

        print("\n=== Surface 3: ClassicLayout ===")

        # 3a. Classic — three-panel view
        capture(page, "classic-01-three-panel", "/classic")

        # 3b. Classic — with uploaded/stub PDF
        # The stub PDF loads automatically without a backend

        print("\n=== HUD Mode (NVIS) ===")

        # 4a. HUD mode on review
        def set_hud(p):
            p.evaluate('document.documentElement.setAttribute("data-distance", "hud")')
            p.wait_for_timeout(300)
        capture(page, "hud-01-review", "/review", actions=set_hud)
        capture(page, "hud-02-quarantine", "/quarantine", actions=set_hud)
        capture(page, "hud-03-classic", "/classic", actions=set_hud)

        # Reset to close distance
        def reset_distance(p):
            p.evaluate('document.documentElement.setAttribute("data-distance", "close")')

        print("\n=== Component Details ===")

        # 5a. NotFound page
        capture(page, "notfound-01", "/nonexistent-route")

        # 5b. Home/Index
        capture(page, "index-01-home", "/")

        print("\n=== Empty States ===")

        # 6a. Quarantine empty (search for nonexistent)
        def empty_quarantine(p):
            search = p.query_selector('input[placeholder*="Search"]') or p.query_selector('input[placeholder*="search"]') or p.query_selector('input[type="text"]')
            if search:
                search.fill("zzzzzznonexistent")
                p.wait_for_timeout(500)
        capture(page, "quarantine-06-empty-state", "/quarantine", actions=empty_quarantine)

        print(f"\nDone! {len(list(OUT.glob('*.png')))} screenshots saved to {OUT}")
        browser.close()


if __name__ == "__main__":
    main()
