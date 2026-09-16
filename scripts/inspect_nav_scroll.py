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
        const header = document.querySelector('header[data-testid="stHeader"]');
        const main = document.querySelector('[data-testid="stMain"]');
        const nav = document.querySelector('.nav-bar-container');
        return {
            headerBox: header ? header.getBoundingClientRect() : null,
            mainBox: main ? main.getBoundingClientRect() : null,
            navBox: nav ? nav.getBoundingClientRect() : null,
            mainPaddingTop: main ? window.getComputedStyle(main).paddingTop : null
        };
    }""")
    print("Positions before scroll:", res)

    # Scroll stMain by 500px
    scroll_res = page.evaluate("""() => {
        const main = document.querySelector('[data-testid="stMain"]');
        main.scrollTop = 500;
        const header = document.querySelector('header[data-testid="stHeader"]');
        const nav = document.querySelector('.nav-bar-container');
        return {
            scrollTop: main.scrollTop,
            headerBox: header ? header.getBoundingClientRect() : null,
            navBox: nav ? nav.getBoundingClientRect() : null
        };
    }""")
    print("Positions after scroll 500px:", scroll_res)

    browser.close()
