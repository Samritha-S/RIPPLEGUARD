"""
test_ui.py - Automated Headless UI/UX Test Suite for RippleGuard's Streamlit Application.
Uses Streamlit AppTest framework (streamlit.testing.v1) to programmatically interact
with widgets, execute runs, and assert on UI state, errors, and rendering consistency.
"""

import os
import sys
import json
import hashlib
import re
import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_manifest_parser import SAMPLE_PACKAGE_LOCK_V3

NPM_GOLDEN_HASH = "9796A34B7A4FA84B52CE6EDCB07B9D0111625289C2EE4AD00ECC8C6E31C6BDAE"
PYPI_GOLDEN_HASH = "E3742E202A69F619934E38415C97CA91E11016CCB4E244C8FAD321A16F7FC487"

APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))


def _calc_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def _get_rendered_fix_order(at: AppTest) -> list:
    pkgs = []
    for m in at.markdown:
        match = re.search(r"#(\d) Priority Fix: <code>([^<]+)</code>", m.value)
        if match:
            pkgs.append(match.group(2))
    return pkgs


def _enter_dashboard_via_demo(at: AppTest) -> AppTest:
    """Helper to click 'Try the Demo Dataset' from landing page and transition to dashboard."""
    demo_btn = [b for b in at.button if "Demo" in b.label][0]
    demo_btn.click().run()
    return at


def test_cold_start_renders_cleanly_and_populates_dashboard():
    """1. Cold start: verify initial render shows Landing Page, 0 exceptions, both cards, and no leaked dashboard."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    # 1. No unhandled exceptions
    assert len(at.exception) == 0, f"App threw exceptions on cold start: {[e.value for e in at.exception]}"

    # 2. Active view defaults to 'landing'
    assert at.session_state["active_view"] == "landing"

    # 3. Landing page branding & cards render non-empty
    markdown_content = "\n".join(m.value for m in at.markdown)
    assert "RippleGuard" in markdown_content
    assert "Upload Your Own Project" in markdown_content
    assert "Analyze your real package-lock.json or SBOM, entirely offline" in markdown_content
    assert "Try the Demo Dataset" in markdown_content
    assert "Explore a real 64-package npm dependency graph, no upload needed" in markdown_content

    # 4. Embedded file uploader in Card 1 and Demo button in Card 2
    assert len(at.file_uploader) == 1
    assert any("Demo" in b.label for b in at.button)

    # 5. Dashboard-only elements (nav bar, KPI metrics, leaderboard dataframe) must NOT be rendered on cold start
    assert len(at.dataframe) == 0
    assert "Jump to:" not in markdown_content
    assert "Analyzed Packages" not in markdown_content


def test_demo_dataset_selection_from_landing_page_transitions_to_dashboard():
    """2. Demo dataset transition: verify clicking 'Try the Demo Dataset' loads the 64-package graph and full dashboard."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    # Click "Try the Demo Dataset" button
    _enter_dashboard_via_demo(at)

    # 1. No exceptions
    assert len(at.exception) == 0, f"App threw exceptions on demo transition: {[e.value for e in at.exception]}"

    # 2. Session state view is dashboard and default package is debug
    assert at.session_state["active_view"] == "dashboard"
    assert at.session_state["selected_package"] == "debug"

    # 3. Top KPI metric cards render non-empty
    markdown_content = "\n".join(m.value for m in at.markdown)
    assert "Analyzed Packages" in markdown_content
    assert "Dependency Links" in markdown_content
    assert "Seed Applications" in markdown_content
    assert "Top Criticality Target" in markdown_content

    # 4. Sticky navigation bar renders with anchor jump links
    assert "Jump to:" in markdown_content
    assert "#graph-section" in markdown_content
    assert "#dossier-section" in markdown_content

    # 5. Leaderboard rendered via st.dataframe with all 64 packages
    assert len(at.dataframe) >= 1
    df = at.dataframe[0].value
    assert len(df) == 64
    assert "Package" in df.columns
    assert "Score" in df.columns
    assert df.iloc[0]["Package"] == "debug"

    # 6. Fix This First panel renders non-empty recommendations
    fix_order = _get_rendered_fix_order(at)
    assert len(fix_order) >= 1
    assert "ms" in fix_order


def test_landing_page_renders_both_cards_and_paths_reachable():
    """3. Landing page cards & paths: verify both cards render and both upload and demo paths are fully reachable."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    markdown_content = "\n".join(m.value for m in at.markdown)
    assert "Upload Your Own Project" in markdown_content
    assert "Try the Demo Dataset" in markdown_content

    # Path 1: Upload path reachable from landing page
    content = json.dumps(SAMPLE_PACKAGE_LOCK_V3).encode("utf-8")
    at.file_uploader[0].upload("package-lock.json", content).run()
    assert len(at.exception) == 0
    assert at.session_state["active_view"] == "dashboard"
    assert len(at.sidebar.selectbox[0].options) == 8

    # Return to landing page via Change Data Source
    chg_btn = [b for b in at.button if "Change Data Source" in b.label][0]
    chg_btn.click().run()
    assert at.session_state["active_view"] == "landing"
    assert len(at.dataframe) == 0

    # Path 2: Demo path reachable from landing page
    demo_btn = [b for b in at.button if "Demo" in b.label][0]
    demo_btn.click().run()
    assert len(at.exception) == 0
    assert at.session_state["active_view"] == "dashboard"
    assert len(at.sidebar.selectbox[0].options) == 64


def test_change_data_source_returns_to_landing_page():
    """4. Return navigation: verify clicking 'Change Data Source' from inside dashboard returns to landing page cleanly."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    # Enter dashboard
    _enter_dashboard_via_demo(at)
    assert at.session_state["active_view"] == "dashboard"
    assert len(at.dataframe) >= 1

    # Click "Change Data Source"
    chg_btn = [b for b in at.button if "Change Data Source" in b.label][0]
    chg_btn.click().run()

    assert len(at.exception) == 0
    assert at.session_state["active_view"] == "landing"
    assert len(at.dataframe) == 0

    # Confirm landing cards are visible again
    markdown_content = "\n".join(m.value for m in at.markdown)
    assert "Upload Your Own Project" in markdown_content
    assert "Try the Demo Dataset" in markdown_content


def test_ecosystem_switch_npm_to_pypi_updates_all_widgets():
    """5. Switch ecosystem radio npm -> PyPI: verify selectbox options, removal of npm nodes, appearance of PyPI nodes."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    _enter_dashboard_via_demo(at)

    assert len(at.sidebar.selectbox[0].options) == 64
    assert "debug" in at.sidebar.selectbox[0].options

    # Switch radio to PyPI
    at.sidebar.radio(key="ecosystem_selector").set_value("PyPI (Python)").run()
    assert len(at.exception) == 0

    # Package selectbox must update to 35 PyPI packages
    pypi_options = at.sidebar.selectbox[0].options
    assert len(pypi_options) == 35
    assert "debug" not in pypi_options
    assert "urllib3" in pypi_options
    assert "requests" in pypi_options
    assert at.session_state["selected_package"] == "requests"

    # Leaderboard must now contain PyPI packages
    assert len(at.dataframe) >= 1
    df_pypi = at.dataframe[0].value
    assert len(df_pypi) == 35
    assert "typing-extensions" in df_pypi["Package"].values


def test_toggle_deterministic_to_monte_carlo_runs_stochastic_simulation():
    """6. Toggle Deterministic -> Monte Carlo: verify mode change and Monte Carlo trial execution."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    _enter_dashboard_via_demo(at)

    # Toggle radio to Monte Carlo
    at.sidebar.radio(key="sim_mode_radio").set_value("Monte Carlo (probability-weighted)").run()
    assert at.session_state["sim_mode_radio"] == "Monte Carlo (probability-weighted)"

    # Click simulate
    sim_btn = [b for b in at.sidebar.button if "Simulate" in b.label][0]
    sim_btn.click().run()
    assert len(at.exception) == 0

    # Verify Monte Carlo caption is rendered with trial count and elapsed timing
    captions = [c.value for c in at.caption]
    mc_caption = next((c for c in captions if "completed in" in c and "heuristic estimate" in c), None)
    assert mc_caption is not None
    assert "1,000 trials" in mc_caption

    # Check that Monte Carlo likelihood card is rendered in Package Risk Dossier
    markdown_content = "\n".join(m.value for m in at.markdown)
    assert "Monte Carlo Infection Likelihood" in markdown_content
    assert "std dev" in markdown_content


def test_ranking_strategy_toggle_coverage_vs_efficiency_reorders_fixes():
    """7. Toggle Coverage vs Efficiency ranking: verify fix order updates dynamically."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    _enter_dashboard_via_demo(at)

    # Default is efficiency: ms, mime-types, on-finished, depd
    eff_order = _get_rendered_fix_order(at)
    assert eff_order == ["ms", "mime-types", "on-finished", "depd"]

    # Toggle to coverage-only ranking
    at.radio(key="ui_fix_ranking_strategy").set_value("Rank by coverage").run()
    assert len(at.exception) == 0
    cov_order = _get_rendered_fix_order(at)
    assert cov_order == ["ms", "mime-types", "depd", "on-finished"]

    # Toggle back to efficiency
    at.radio(key="ui_fix_ranking_strategy").set_value("Rank by efficiency (coverage per effort)").run()
    assert _get_rendered_fix_order(at) == ["ms", "mime-types", "on-finished", "depd"]


def test_package_change_clears_prior_simulation_state():
    """8. Select package A, simulate, then select package B: verify prior simulation state is cleared."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    _enter_dashboard_via_demo(at)

    # Simulate on package A (debug)
    sim_btn = [b for b in at.sidebar.button if "Simulate" in b.label][0]
    sim_btn.click().run()
    assert at.session_state["compromised_nodes"] == ["debug"]

    # Select package B (express) without clicking reset
    at.sidebar.selectbox[0].set_value("express").run()
    assert at.session_state["selected_package"] == "express"
    assert at.session_state["compromised_node"] is None
    assert at.session_state["compromised_nodes"] == []


def test_manifest_upload_and_revert_to_demo_dataset():
    """9. Upload custom manifest SBOM: verify node count changes, then click Revert to restore demo graph."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    # Upload 8-package sample lockfile directly from landing page
    content = json.dumps(SAMPLE_PACKAGE_LOCK_V3).encode("utf-8")
    at.file_uploader[0].upload("package-lock.json", content).run()
    assert len(at.exception) == 0
    assert at.session_state["active_view"] == "dashboard"
    assert len(at.sidebar.selectbox[0].options) == 8

    # Revert to demo dataset
    revert_btn = [b for b in at.button if "Return to Demo Dataset" in b.label][0]
    revert_btn.click().run()
    assert len(at.exception) == 0
    assert len(at.sidebar.selectbox[0].options) == 64


def test_malformed_manifest_upload_displays_readable_error():
    """10. Upload malformed JSON: verify clean error alert and no leaked Python traceback."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    at.file_uploader[0].upload("corrupt.json", b"{this is not valid json").run()
    assert len(at.exception) == 0
    assert len(at.error) >= 1
    err_msg = at.error[0].value
    assert "Manifest parsing error" in err_msg
    assert "Traceback" not in err_msg
    assert at.session_state["active_view"] == "landing"


def test_zero_downstream_dotenv_simulation_messaging():
    """11. Simulate on dotenv: verify dedicated contained/zero-downstream root message."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    _enter_dashboard_via_demo(at)

    at.sidebar.selectbox[0].set_value("dotenv").run()
    sim_btn = [b for b in at.sidebar.button if "Simulate" in b.label][0]
    sim_btn.click().run()
    assert len(at.exception) == 0

    markdown_content = "\n".join(m.value for m in at.markdown)
    assert "Zero-Downstream Root Application" in markdown_content
    assert "completely contained" in markdown_content


def test_all_zero_weight_sliders_trigger_equal_weighting_warning_and_scores():
    """12. Zero sliders: verify equal-weighting warning and 25% equal weighting split."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    _enter_dashboard_via_demo(at)

    at.slider(key="w_cvss").set_value(0)
    at.slider(key="w_trans").set_value(0)
    at.slider(key="w_indeg").set_value(0)
    at.slider(key="w_between").set_value(0).run()

    assert len(at.exception) == 0
    warnings = [w.value for w in at.warning]
    assert any("defaulting to equal weighting (25% each)" in w for w in warnings)

    # Effective weighting string shows 25% for each of the 4 dimensions
    markdown_content = "\n".join(m.value for m in at.markdown)
    assert "Effective: <b>25%</b> CVSS | <b>25%</b> Trans | <b>25%</b> In-Deg | <b>25%</b> Between" in markdown_content


def test_max_betweenness_slider_ranks_bridge_bottlenecks():
    """13. 100% betweenness slider: verify bridge bottleneck http-errors elevates to top rank."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    _enter_dashboard_via_demo(at)

    at.slider(key="w_cvss").set_value(0)
    at.slider(key="w_trans").set_value(0)
    at.slider(key="w_indeg").set_value(0)
    at.slider(key="w_between").set_value(100).run()

    assert len(at.exception) == 0
    df = at.dataframe[0].value
    assert len(df) == 64
    assert df.iloc[0]["Package"] == "http-errors"
    assert df.iloc[0]["Score"] == 100.0


def test_regression_guard_dataset_hashes_unchanged():
    """14. Regression guard: ensure running the test suite leaves dataset caches bit-for-bit unchanged."""
    npm_path = os.path.join("data", "dependency_graph.json")
    pypi_path = os.path.join("data", "dependency_graph_pypi.json")

    assert _calc_sha256(npm_path) == NPM_GOLDEN_HASH, "data/dependency_graph.json has been modified!"
    assert _calc_sha256(pypi_path) == PYPI_GOLDEN_HASH, "data/dependency_graph_pypi.json has been modified!"


def test_tutorial_onboarding_section_renders_in_dashboard():
    """15. Tutorial/Onboarding section: verify Quick Start, SBOM guide, privacy note, and glossary render in dashboard."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    _enter_dashboard_via_demo(at)

    assert len(at.exception) == 0
    markdown_content = "\n".join(m.value for m in at.markdown)

    # Verify Quick Start Guide
    assert "Quick Start Guide" in markdown_content
    assert "1. EXPLORE GRAPH" in markdown_content
    assert "2. SIMULATE ATTACK" in markdown_content
    assert "3. ANALYZE YOUR PROJECT" in markdown_content
    assert "4. FIX THIS FIRST" in markdown_content

    # Verify Analyze Your Own Project subsection
    assert "Analyze Your Own Project" in markdown_content
    assert "package-lock.json" in markdown_content
    assert "CycloneDX" in markdown_content

    # Verify Privacy & Security Guarantee
    assert "processed entirely offline" in markdown_content
    assert "No proprietary code" in markdown_content

    # Verify Glossary
    assert "Criticality Score" in markdown_content
    assert "Blast Radius" in markdown_content
    assert "Hidden Critical" in markdown_content
    assert "Deterministic vs. Monte Carlo" in markdown_content

