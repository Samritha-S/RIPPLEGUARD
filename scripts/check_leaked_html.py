import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:8501", wait_until="networkidle")
    page.wait_for_selector(".header-title", timeout=20000)

    # Find all pre and code elements on the page
    code_elements = page.locator("pre, code")
    count = code_elements.count()
    print(f"Total <pre> and <code> elements found: {count}")
    
    leaked_html = []
    for i in range(count):
        el = code_elements.nth(i)
        text = el.inner_text()
        if "<div" in text or "<span" in text or "style=" in text or "class=" in text or "<b" in text:
            leaked_html.append((i, el.evaluate("el => el.tagName"), text[:120]))
    
    print(f"\n❌ Leaked HTML count: {len(leaked_html)}")
    for idx, tag, snippet in leaked_html:
        print(f"  [{idx}] <{tag}>: {snippet.replace(chr(10), ' ')}")

    browser.close()
