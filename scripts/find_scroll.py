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

    scrollable_el = page.evaluate("""() => {
        let el = document.querySelector('.main') || document.querySelector('[data-testid="stMain"]') || document.querySelector('[data-testid="stAppViewContainer"]');
        let allEls = Array.from(document.querySelectorAll('*'));
        let scrollable = [];
        for (let e of allEls) {
            if (e.scrollHeight > e.clientHeight + 50) {
                scrollable.push({
                    tag: e.tagName,
                    id: e.id,
                    className: e.className,
                    testId: e.getAttribute('data-testid'),
                    scrollHeight: e.scrollHeight,
                    clientHeight: e.clientHeight,
                    scrollTop: e.scrollTop
                });
            }
        }
        return scrollable;
    }""")
    print(f"Found {len(scrollable_el)} scrollable elements:")
    for s in scrollable_el:
        print("  ", s)

    browser.close()
