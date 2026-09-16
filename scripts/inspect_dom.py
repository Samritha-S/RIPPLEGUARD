import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:8501", wait_until="networkidle")
    page.wait_for_selector(".header-title", timeout=25000)

    res = page.evaluate("""() => {
        const appView = document.querySelector('[data-testid="stAppViewContainer"]');
        const main = document.querySelector('section.main');
        const doc = document.documentElement;
        return {
            windowScrollY: window.scrollY,
            appViewScrollTop: appView ? appView.scrollTop : null,
            mainScrollTop: main ? main.scrollTop : null,
            appViewScrollHeight: appView ? appView.scrollHeight : null,
            mainScrollHeight: main ? main.scrollHeight : null,
            docScrollHeight: doc.scrollHeight
        };
    }""")
    print("Scroll container info:", res)

    # Let's check which element actually scrolls
    scroll_res = page.evaluate("""() => {
        const appView = document.querySelector('[data-testid="stAppViewContainer"]');
        appView.scrollTop = 500;
        return {
            afterScrollTop: appView.scrollTop
        };
    }""")
    print("appView scrollTop test:", scroll_res)

    # Check anchor elements
    for sec in ["#graph-section", "#dossier-section", "#fix-section", "#leaderboard-section"]:
        el = page.locator(sec)
        print(f"{sec}: count={el.count()}")
        if el.count() > 0:
            print(f"   box={el.first.bounding_box()}")

    # Check all columns on page
    cols = page.locator('[data-testid="column"]').all()
    print(f"Total column elements: {len(cols)}")
    for idx, c in enumerate(cols):
        print(f"  Col {idx}: box={c.bounding_box()}")

    # Check dataframe
    dfs = page.locator('[data-testid="stDataFrame"]').all()
    print(f"Dataframe count: {len(dfs)}")
    if dfs:
        print("Dataframe text preview:", dfs[0].inner_text()[:200])

    browser.close()
