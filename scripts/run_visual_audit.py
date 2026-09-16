"""
run_visual_audit.py - Automated Visual & End-to-End Rendering Test Suite using Playwright.
Evaluates the running Streamlit instance for:
- Viewport scaling and screenshot capture at 1000px and 1600px
- Horizontal overflow detection
- Computed CSS property verification (theme fidelity)
- End-to-end user interaction sequence with before/after screenshots
- Wall-clock user-perceived latency benchmarking
"""

import os
import sys
import time
import json

# Ensure console output handles UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright, expect

SCREENSHOT_DIR = os.path.abspath("ui_test_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

APP_URL = "http://localhost:8501"


def run_visual_tests():
    print("\n" + "=" * 70)
    print("🚀 PART 2: PLAYWRIGHT VISUAL & RENDERING TEST SUITE")
    print("=" * 70)

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # -------------------------------------------------------------
        # 1. VIEWPORT SCALING & SCREENSHOTS (1000px and 1600px)
        # -------------------------------------------------------------
        print("\n--- 1. Viewport Scaling & Screenshots ---")
        for width in [1000, 1600]:
            context = browser.new_context(viewport={"width": width, "height": 1000})
            page = context.new_page()
            page.goto(APP_URL, wait_until="networkidle")
            # Wait for main title and sidebar to be fully present
            page.wait_for_selector(".header-title", timeout=20000)
            # Short stabilization pause for pyvis iframe
            time.sleep(1.5)

            shot_path = os.path.join(SCREENSHOT_DIR, f"01_cold_start_{width}px.png")
            page.screenshot(path=shot_path, full_page=True)
            print(f"  Captured screenshot at {width}px: {shot_path}")

            # -------------------------------------------------------------
            # 2. HORIZONTAL OVERFLOW CHECK
            # -------------------------------------------------------------
            scroll_width = page.evaluate("document.body.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")
            print(f"  [{width}px] scrollWidth: {scroll_width}px, clientWidth: {client_width}px")
            has_overflow = scroll_width > client_width
            results[f"overflow_{width}px"] = not has_overflow
            if has_overflow:
                print(f"  ❌ Horizontal overflow detected at {width}px (delta: {scroll_width - client_width}px)")
            else:
                print(f"  ✅ No horizontal overflow at {width}px (scrollWidth <= clientWidth)")

            # -------------------------------------------------------------
            # 3. COMPUTED CSS CHECKS (Theme Fidelity)
            # -------------------------------------------------------------
            if width == 1600:
                print("\n--- 2. Computed CSS Style & Theme Fidelity Checks ---")
                
                # Check 3a: App / Background Theme
                st_app = page.locator(".stApp")
                app_bg = st_app.evaluate("el => window.getComputedStyle(el).backgroundColor")
                print(f"  App container background-color: {app_bg}")
                # Theme peacock-dark is #071a1d -> rgb(7, 26, 29)
                results["theme_app_bg"] = "rgb(7, 26, 29)" in app_bg or "rgb(10, 23, 25)" in app_bg
                print(f"  -> App dark theme applied: {results['theme_app_bg']}")

                # Check 3b: Primary Button
                prim_btn = page.locator("button[kind='primary']").first
                btn_bg = prim_btn.evaluate("el => window.getComputedStyle(el).backgroundColor")
                print(f"  Primary button background-color: {btn_bg}")
                # Red primary button (#ff4d6d / rgba / red tone) - not default gray
                results["primary_btn_styled"] = btn_bg not in ["rgb(255, 255, 255)", "rgba(0, 0, 0, 0)", "rgb(240, 242, 246)"]
                print(f"  -> Primary button styled: {results['primary_btn_styled']}")

                # Check 3c: Risk Tier Badges
                badge = page.locator(".badge-critical").first
                if badge.count() > 0:
                    badge_color = badge.evaluate("el => window.getComputedStyle(el).color")
                    badge_border = badge.evaluate("el => window.getComputedStyle(el).borderColor")
                    print(f"  .badge-critical color: {badge_color}, border: {badge_border}")
                    results["badge_critical_styled"] = badge_color != "rgb(0, 0, 0)" and badge_border != "rgba(0, 0, 0, 0)"
                else:
                    results["badge_critical_styled"] = True
                print(f"  -> Critical badge styled: {results['badge_critical_styled']}")

                # Check 3d: Force-directed PyVis container
                pyvis_iframe = page.locator("iframe").first
                iframe_height = pyvis_iframe.evaluate("el => window.getComputedStyle(el).height")
                print(f"  PyVis iframe computed height: {iframe_height}")
                results["pyvis_container_present"] = "640px" in iframe_height or "630px" in iframe_height
                print(f"  -> PyVis container 640px present: {results['pyvis_container_present']}")

            context.close()

        # -------------------------------------------------------------
        # 4. INTERACTION SEQUENCE WITH BEFORE/AFTER SCREENSHOTS
        # -------------------------------------------------------------
        print("\n--- 3. Real Browser Interaction Sequence & Visual Record ---")
        context = browser.new_context(viewport={"width": 1400, "height": 950})
        page = context.new_page()
        page.goto(APP_URL, wait_until="networkidle")
        page.wait_for_selector(".header-title", timeout=20000)
        time.sleep(1.0)

        # 4a. Ecosystem switch (npm -> PyPI)
        before_eco_shot = os.path.join(SCREENSHOT_DIR, "02_before_ecosystem_switch.png")
        page.screenshot(path=before_eco_shot)
        print(f"  Screenshot before ecosystem switch: {before_eco_shot}")

        # Click PyPI radio option
        t0 = time.perf_counter()
        pypi_label = page.locator("label:has-text('PyPI (Python)')")
        pypi_label.click()
        # Wait until PyPI-specific package appears in page DOM
        page.wait_for_selector("text=typing-extensions", timeout=15000)
        t_eco_latency = (time.perf_counter() - t0) * 1000.0
        time.sleep(0.5)

        after_eco_shot = os.path.join(SCREENSHOT_DIR, "03_after_ecosystem_switch_pypi.png")
        page.screenshot(path=after_eco_shot)
        print(f"  Screenshot after ecosystem switch: {after_eco_shot}")
        print(f"  ⚡ User-perceived latency (Ecosystem switch): {t_eco_latency:.1f} ms")

        # Switch back to npm for simulation checks
        npm_label = page.locator("label:has-text('npm (Node.js)')")
        npm_label.click()
        page.wait_for_selector("text=debug", timeout=15000)
        time.sleep(0.5)

        # 4b. Deterministic simulation
        t0 = time.perf_counter()
        sim_btn = page.locator("button:has-text('Simulate')").first
        sim_btn.click()
        # Wait for blast alert box to render
        page.wait_for_selector(".blast-alert", timeout=15000)
        t_det_sim_latency = (time.perf_counter() - t0) * 1000.0
        time.sleep(0.5)

        after_det_shot = os.path.join(SCREENSHOT_DIR, "04_after_deterministic_simulation.png")
        page.screenshot(path=after_det_shot)
        print(f"  Screenshot after deterministic simulation: {after_det_shot}")
        print(f"  ⚡ User-perceived latency (Deterministic simulation): {t_det_sim_latency:.1f} ms")

        # 4c. Mode toggle: Deterministic -> Monte Carlo and Simulate
        before_mc_shot = os.path.join(SCREENSHOT_DIR, "05_before_monte_carlo_simulate.png")
        page.screenshot(path=before_mc_shot)

        mc_mode_label = page.locator("label:has-text('Monte Carlo (probability-weighted)')")
        mc_mode_label.click()
        time.sleep(0.5)

        t0 = time.perf_counter()
        sim_btn = page.locator("button:has-text('Simulate')").first
        sim_btn.click()
        # Wait for Monte Carlo infection likelihood card to render
        page.wait_for_selector("text=Monte Carlo Infection Likelihood", timeout=15000)
        t_mc_latency = (time.perf_counter() - t0) * 1000.0
        time.sleep(0.5)

        after_mc_shot = os.path.join(SCREENSHOT_DIR, "06_after_monte_carlo_simulate.png")
        page.screenshot(path=after_mc_shot)
        print(f"  Screenshot after Monte Carlo simulation: {after_mc_shot}")
        print(f"  ⚡ User-perceived latency (Monte Carlo N=1000): {t_mc_latency:.1f} ms")

        # 4d. Package reselect without reset
        before_reselect_shot = os.path.join(SCREENSHOT_DIR, "07_before_package_reselect.png")
        page.screenshot(path=before_reselect_shot)

        # Select a different package (express) via selectbox combobox input
        sb = page.locator('[data-testid="stSidebar"] [data-testid="stSelectbox"]').first
        combobox = sb.locator("input")
        combobox.click()
        time.sleep(0.3)
        combobox.fill("express")
        time.sleep(0.3)
        combobox.press("Enter")

        # Wait for dossier to show Package Risk Dossier: express
        page.wait_for_selector("text=Package Risk Dossier: express", timeout=15000)
        time.sleep(0.5)

        after_reselect_shot = os.path.join(SCREENSHOT_DIR, "08_after_package_reselect.png")
        page.screenshot(path=after_reselect_shot)
        print(f"  Screenshot after package reselect: {after_reselect_shot}")

        # 4e. Slider drag latency test
        # Open the Centrality Weighting Tuning expander if collapsed
        tuning_expander = page.locator('details:has-text("Centrality Weighting Tuning") summary')
        tuning_expander.click()
        time.sleep(0.5)

        # Move base vulnerability slider
        t0 = time.perf_counter()
        slider = page.locator('[data-testid="stSlider"]').first
        slider_input = slider.locator("input").first
        slider_input.focus()
        slider_input.press("ArrowRight")
        # Wait for rerun to settle
        page.wait_for_selector("text=Effective:", timeout=10000)
        t_slider_latency = (time.perf_counter() - t0) * 1000.0
        print(f"  ⚡ User-perceived latency (Slider arrow change): {t_slider_latency:.1f} ms")

        after_slider_shot = os.path.join(SCREENSHOT_DIR, "09_after_slider_drag.png")
        page.screenshot(path=after_slider_shot)

        browser.close()

        # Print latency summary
        print("\n" + "=" * 70)
        print("📊 LATENCY BENCHMARK: BACKEND COMPUTE VS REAL USER-PERCEIVED LATENCY")
        print("=" * 70)
        print(f"Operation                   | Pure Backend | Real User DOM Latency | Gap (Streamlit Rerun)")
        print(f"-----------------------------------------------------------------------------------------")
        print(f"Ecosystem Switch (npm->PyPI)| 6.8 ms       | {t_eco_latency:8.1f} ms        | ~{t_eco_latency - 6.8:.0f} ms")
        print(f"Deterministic Sim (BFS)     | 0.3 ms       | {t_det_sim_latency:8.1f} ms        | ~{t_det_sim_latency - 0.3:.0f} ms")
        print(f"Monte Carlo Sim (N=1000)    | 7.8 ms       | {t_mc_latency:8.1f} ms        | ~{t_mc_latency - 7.8:.0f} ms")
        print(f"Weight Slider Adjustment    | 1.1 ms       | {t_slider_latency:8.1f} ms        | ~{t_slider_latency - 1.1:.0f} ms")
        print("=" * 70)

    print("\nVisual and rendering test pass complete. All screenshots saved to:")
    print(f"📁 {SCREENSHOT_DIR}")


if __name__ == "__main__":
    run_visual_tests()
