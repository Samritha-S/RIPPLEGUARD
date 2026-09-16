"""
RippleGuard - Explainable Dependency-Risk Analysis Tool
Hackathon Submission: UN SDG 9 (Industry, Innovation and Infrastructure)
Phase A: Foundation Data Models, Graph Versioning, Configurable Weights,
Hidden Critical Detection, and Interactive Leaderboard.
"""

import os
import sys
import streamlit as st
import streamlit.components.v1 as components

# Ensure local imports work reliably
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.fetcher import (
    load_cached_graph,
    load_cached_pypi_graph,
    get_cached_or_fetch_graph,
    get_cached_or_fetch_pypi_graph
)
from src.models import WeightingConfig
from src.graph_builder import build_dependency_graph, compute_structural_metrics
from src.scoring import (
    compute_composite_criticality,
    generate_explanation,
    get_mitigations_for_tier
)
from src.simulator import simulate_compromise, simulate_monte_carlo
from src.visualizer import create_pyvis_graph
from src.fix_consolidator import consolidate_fixes
from src.manifest_parser import parse_manifest_content, ManifestParseError
from src.exporter import generate_scenario_report
from src.osv_client import query_osv_package, query_osv_batch

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="RippleGuard | Supply Chain Risk Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# Theme & Custom CSS (Peacock Green & Lavender Palette)
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    /* Theme Colors: Peacock Green (#005f73, #0a4d5c) & Lavender (#b388eb, #c8b6ff) */
    :root {
        --peacock-dark: #071a1d;
        --peacock-primary: #005f73;
        --peacock-light: #0a9396;
        --peacock-border: #15454d;
        --lavender-accent: #c8b6ff;
        --lavender-vibrant: #b388eb;
        --lavender-light: #e7c6ff;
        --bg-surface: #0a1719;
        --text-bright: #f0f7f8;
        --text-muted: #9bb3b8;
    }

    /* Main Container Styles */
    .stApp {
        background-color: var(--peacock-dark);
        color: var(--text-bright);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* Header Banner */
    .header-box {
        background: linear-gradient(135deg, #003844 0%, #005f73 50%, #2b1b42 100%);
        border: 1px solid var(--peacock-border);
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .header-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.5px;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .header-subtitle {
        color: var(--lavender-light);
        font-size: 1.05rem;
        margin-top: 6px;
        margin-bottom: 0;
    }
    .sdg-tag {
        display: inline-block;
        background: rgba(200, 182, 255, 0.15);
        color: var(--lavender-accent);
        border: 1px solid var(--lavender-vibrant);
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 10px;
    }

    /* Metric KPI Cards */
    .metric-card {
        background: rgba(10, 23, 25, 0.75);
        border: 1px solid var(--peacock-border);
        border-radius: 10px;
        padding: 14px 18px;
        text-align: center;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: var(--lavender-vibrant);
        transform: translateY(-2px);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--text-bright);
        margin: 2px 0;
    }
    .metric-label {
        font-size: 0.8rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }

    /* Risk Badges */
    .badge-critical {
        background-color: rgba(230, 57, 70, 0.2);
        color: #ff6b6b;
        border: 1px solid #e63946;
        padding: 3px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .badge-high {
        background-color: rgba(244, 162, 97, 0.2);
        color: #f4a261;
        border: 1px solid #f4a261;
        padding: 3px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .badge-medium {
        background-color: rgba(179, 136, 235, 0.2);
        color: var(--lavender-accent);
        border: 1px solid var(--lavender-vibrant);
        padding: 3px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .badge-low {
        background-color: rgba(10, 147, 150, 0.2);
        color: #0a9396;
        border: 1px solid #0a9396;
        padding: 3px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
    }

    /* Panel Boxes */
    .panel-card {
        background: #091a1d;
        border: 1px solid var(--peacock-border);
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }
    .panel-title {
        color: var(--lavender-accent);
        font-size: 1.15rem;
        font-weight: 700;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Blast Radius Alert Box */
    .blast-alert {
        background: linear-gradient(135deg, rgba(142, 45, 226, 0.2) 0%, rgba(255, 77, 109, 0.2) 100%);
        border: 1px solid var(--lavender-vibrant);
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 16px;
    }

    /* Custom scrollbars */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-thumb {
        background: var(--peacock-border);
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--lavender-vibrant);
    }

    /* Sticky In-Page Navigation Bar */
    div[data-testid="stElementContainer"]:has(.nav-bar-container) {
        position: sticky !important;
        top: 60px !important;
        z-index: 990 !important;
    }
    .nav-bar-container {
        background: rgba(7, 26, 29, 0.94);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid var(--peacock-border);
        border-radius: 8px;
        padding: 8px 16px;
        margin-top: 10px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
    }
    .nav-bar-label {
        font-size: 0.78rem;
        color: var(--text-muted);
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }
    .nav-bar-links {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }
    .nav-link-btn {
        color: var(--lavender-accent) !important;
        text-decoration: none !important;
        font-size: 0.82rem;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 6px;
        background: rgba(200, 182, 255, 0.08);
        border: 1px solid rgba(200, 182, 255, 0.2);
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .nav-link-btn:hover {
        background: rgba(200, 182, 255, 0.22);
        color: #ffffff !important;
        border-color: var(--lavender-vibrant);
        transform: translateY(-1px);
    }

    /* Anchor targets offset for sticky navigation */
    .section-anchor {
        scroll-margin-top: 7.5rem;
        display: block;
        height: 0;
        visibility: hidden;
    }

    /* Priority Fix Card */
    .priority-fix-card {
        background: rgba(0, 0, 0, 0.25);
        border: 1px solid #1a3c42;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 12px;
        box-sizing: border-box;
        height: auto !important;
        min-height: auto !important;
        overflow: visible !important;
    }

    /* Section Spacing */
    .section-spacing {
        margin-top: 24px;
        margin-bottom: 24px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def render_html(html_str: str) -> None:
    """Render an HTML string cleanly via st.markdown with leading line whitespace stripped
    to prevent CommonMark indented-code-block (<pre><code>) triggering."""
    cleaned = "\n".join(line.strip() for line in html_str.strip().splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)

# ---------------------------------------------------------
# Load Data & Construct Graph (Cached Topology or Uploaded Manifest)
# ---------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_demo_graph_data():
    try:
        raw_data = load_cached_graph()
    except FileNotFoundError as err:
        st.error(str(err))
        st.stop()

    G = build_dependency_graph(raw_data)
    metrics = compute_structural_metrics(G)

    max_in = max((m["in_degree"] for m in metrics.values()), default=1)
    max_trans = max((m["transitive_dependents_count"] for m in metrics.values()), default=1)

    return raw_data, G, metrics, max_in, max_trans


@st.cache_data(show_spinner=False)
def load_pypi_graph_data():
    try:
        raw_data = load_cached_pypi_graph()
    except FileNotFoundError as err:
        st.error(str(err))
        st.stop()

    G = build_dependency_graph(raw_data)
    metrics = compute_structural_metrics(G)

    max_in = max((m["in_degree"] for m in metrics.values()), default=1)
    max_trans = max((m["transitive_dependents_count"] for m in metrics.values()), default=1)

    return raw_data, G, metrics, max_in, max_trans


@st.cache_data(show_spinner=False)
def fetch_cached_osv_cvss(pkg_name: str, ecosystem: str):
    return query_osv_package(pkg_name, ecosystem)


# Check if user uploaded a custom manifest or selected PyPI
uploaded_file = st.session_state.get("manifest_uploader")
selected_ecosystem = st.session_state.get("ecosystem_selector", "npm (Node.js)")
manifest_error = None

if uploaded_file is not None:
    try:
        raw_data = parse_manifest_content(uploaded_file.getvalue(), filename=uploaded_file.name)
        G = build_dependency_graph(raw_data)
        metrics = compute_structural_metrics(G)
        max_in = max((m["in_degree"] for m in metrics.values()), default=1)
        max_trans = max((m["transitive_dependents_count"] for m in metrics.values()), default=1)
        active_source_label = f"Uploaded: {uploaded_file.name}"
        is_custom_upload = True
    except ManifestParseError as err:
        manifest_error = str(err)
        raw_data, G, metrics, max_in, max_trans = load_demo_graph_data()
        active_source_label = "Demo dataset (5 npm seeds)"
        is_custom_upload = False
elif "PyPI" in selected_ecosystem:
    raw_data, G, metrics, max_in, max_trans = load_pypi_graph_data()
    active_source_label = "Demo dataset (5 PyPI seeds)"
    is_custom_upload = False
else:
    raw_data, G, metrics, max_in, max_trans = load_demo_graph_data()
    active_source_label = "Demo dataset (5 npm seeds)"
    is_custom_upload = False

max_bw = max((m.get("betweenness_centrality", 0.0) for m in metrics.values()), default=0.0)
betweenness_skipped = any(m.get("betweenness_skipped", False) for m in metrics.values()) or len(G) > 500

# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
all_available_packages = sorted(list(G.nodes()))
if "selected_package" not in st.session_state or st.session_state.selected_package not in all_available_packages:
    if "debug" in all_available_packages:
        st.session_state.selected_package = "debug"
    elif "requests" in all_available_packages:
        st.session_state.selected_package = "requests"
    else:
        seeds_list = [s for s in raw_data.get("metadata", {}).get("seeds", []) if s in all_available_packages]
        st.session_state.selected_package = seeds_list[0] if seeds_list else all_available_packages[0]

if "compromised_node" not in st.session_state or (st.session_state.compromised_node and not any(n in all_available_packages for n in ([st.session_state.compromised_node] if isinstance(st.session_state.compromised_node, str) else st.session_state.compromised_node))):
    st.session_state.compromised_node = None
if "compromised_nodes" not in st.session_state:
    st.session_state.compromised_nodes = []

# ---------------------------------------------------------
# Sidebar Controls & Weighting Tuning (FR-3.3)
# ---------------------------------------------------------
with st.sidebar:
    render_html(
        """
        <h3 style="color:#c8b6ff; margin-bottom:8px;">⚙️ RippleGuard Controls</h3>
        <p style="color:#9bb3b8; font-size:0.85rem;">
            Inspect structural fragility across the open-source dependency ecosystem.
        </p>
        """
    )

    ecosystem_choice = st.radio(
        "🌐 Ecosystem:",
        options=["npm (Node.js)", "PyPI (Python)"],
        index=0 if "PyPI" not in selected_ecosystem else 1,
        key="ecosystem_selector",
        help="Select open-source registry ecosystem to inspect or live-fetch.",
        on_change=lambda: st.session_state.pop("selected_package", None)
    )

    # Active Graph Source Indicator
    render_html(
        f"""
        <div style="background:rgba(0, 95, 115, 0.25); border:1px solid #0a9396; border-radius:6px; padding:6px 12px; margin-bottom:14px;">
            <span style="font-size:0.75rem; color:#9bb3b8; text-transform:uppercase; font-weight:600;">Active Graph Source:</span><br/>
            <span style="font-size:0.88rem; font-weight:700; color:{'#ffb703' if is_custom_upload else '#c8b6ff'};">
                {'📂 ' if is_custom_upload else '🛡️ '}{active_source_label}
            </span>
        </div>
        """
    )

    all_packages = sorted(list(G.nodes()))
    default_idx = all_packages.index(st.session_state.selected_package) if st.session_state.selected_package in all_packages else 0

    selected_pkg = st.selectbox(
        "🔍 Select Package to Inspect:",
        options=all_packages,
        index=default_idx,
        help="Select any package to evaluate its structural reach, criticality score, and explainable risk."
    )

    if selected_pkg != st.session_state.selected_package:
        st.session_state.selected_package = selected_pkg
        st.session_state.compromised_node = None
        st.session_state.compromised_nodes = []
        st.rerun()

    st.markdown("---")
    st.markdown("<h4 style='color:#c8b6ff;'>💥 Compromise Simulation</h4>", unsafe_allow_html=True)

    # FR-4.4: Simulation mode toggle — shown BEFORE origins so users pick mode first
    sim_mode = st.radio(
        "Propagation Mode:",
        options=["Deterministic (worst-case)", "Monte Carlo (probability-weighted)"],
        index=0,
        key="sim_mode_radio",
        help="Deterministic BFS shows whether each downstream node is reachable (binary). Monte Carlo runs N probabilistic trials to estimate per-node infection probability based on version pin constraints.",
        horizontal=True
    )
    use_monte_carlo = sim_mode == "Monte Carlo (probability-weighted)"

    if use_monte_carlo:
        mc_n_trials = st.slider(
            "Trials (N):", min_value=100, max_value=5000, value=1000, step=100,
            key="mc_n_trials",
            help="Number of Monte Carlo trials. More trials = more stable probability estimates. 1000 completes in ~10ms on demo graphs."
        )

    # FR-4.3: Multi-select origin packages
    sim_default = st.session_state.compromised_nodes if st.session_state.compromised_nodes else [st.session_state.selected_package]
    sim_selected = st.multiselect(
        "Select Origin(s) to Compromise:",
        options=all_packages,
        default=sim_default,
        key="sim_origins_multiselect",
        help="Select one or multiple packages to simulate supply-chain compromise propagation and overlapping blast radii."
    )

    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        if st.button("🚨 Simulate", use_container_width=True, type="primary"):
            chosen = sim_selected if sim_selected else [st.session_state.selected_package]
            st.session_state.compromised_nodes = chosen
            st.session_state.compromised_node = ", ".join(chosen) if len(chosen) > 1 else chosen[0]
            st.rerun()

    with sim_col2:
        if st.button("↺ Reset", use_container_width=True):
            st.session_state.compromised_node = None
            st.session_state.compromised_nodes = []
            st.rerun()

    st.markdown("---")
    # Live OSV.dev Vulnerability Data Toggle (Default OFF)
    use_live_osv = st.toggle(
        "🔍 Use live OSV.dev data",
        value=False,
        help="Query live OSV.dev API for real-time advisory CVSS scores (falls back to curated/default if unavailable)."
    )


    st.markdown("---")
    # FR-3.3 & FR-3.1: Configurable Centrality Weighting Sliders
    with st.expander("⚖️ Centrality Weighting Tuning", expanded=False):
        st.markdown("<div style='font-size:0.8rem; color:#9bb3b8; margin-bottom:6px;'>Tune relative weights between structural blast radius, shortest-path bottleneck position, and CVE severity:</div>", unsafe_allow_html=True)
        w_cvss = st.slider("Base Vulnerability (CVSS)", min_value=0, max_value=100, value=35, step=5, key="w_cvss")
        w_trans = st.slider("Transitive Blast Reach", min_value=0, max_value=100, value=40, step=5, key="w_trans")
        w_indeg = st.slider("Direct In-Degree Dependents", min_value=0, max_value=100, value=25, step=5, key="w_indeg")
        w_between = st.slider(
            "Betweenness Centrality (Bridge)",
            min_value=0,
            max_value=100,
            value=0,
            step=5,
            key="w_between",
            disabled=betweenness_skipped,
            help="Weight of shortest-path bridge bottleneck position in the dependency graph (defaults to 0%)."
        )

        if betweenness_skipped:
            st.info("Betweenness centrality not computed live for graphs over 500 nodes")

        all_zero = (w_cvss + w_trans + w_indeg + w_between) == 0
        if all_zero:
            active_weight_cfg = WeightingConfig(0.25, 0.25, 0.25, 0.25)
            st.warning("All weights are 0 — defaulting to equal weighting (25% each).", icon="⚠️")
        else:
            active_weight_cfg = WeightingConfig(
                weight_cvss=w_cvss / 100.0,
                weight_transitive=w_trans / 100.0,
                weight_indegree=w_indeg / 100.0,
                weight_betweenness=(0.0 if betweenness_skipped else w_between / 100.0)
            ).normalize()

        eff_bw = f" | <b>{int(round(active_weight_cfg.weight_betweenness*100))}%</b> Between" if active_weight_cfg.weight_betweenness > 0 else ""
        st.markdown(
            f"<div style='font-size:0.75rem; color:#c8b6ff; margin-top:4px;'>Effective: <b>{int(round(active_weight_cfg.weight_cvss*100))}%</b> CVSS | <b>{int(round(active_weight_cfg.weight_transitive*100))}%</b> Trans | <b>{int(round(active_weight_cfg.weight_indegree*100))}%</b> In-Deg{eff_bw}</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")
    # Manifest / SBOM Upload
    with st.expander("📂 Upload Manifest / SBOM", expanded=is_custom_upload):
        st.markdown(
            "<div style='font-size:0.8rem; color:#9bb3b8; margin-bottom:6px;'>"
            "Upload an npm <code>package-lock.json</code> or CycloneDX JSON SBOM to evaluate your project's custom supply chain graph:"
            "</div>",
            unsafe_allow_html=True
        )
        uploaded_manifest_widget = st.file_uploader(
            "Upload package-lock.json or CycloneDX JSON",
            type=["json"],
            key="manifest_uploader",
            help="Upload an npm package-lock.json or CycloneDX JSON SBOM to evaluate your own project's dependency graph."
        )
        if manifest_error:
            st.error(f"Manifest parsing error: {manifest_error}")
        if is_custom_upload:
            st.success(f"Loaded {len(G.nodes())} packages and {len(G.edges())} dependency edges.")
            if st.button("↺ Return to Demo Dataset", key="reset_demo_btn"):
                del st.session_state["manifest_uploader"]
                st.rerun()

    # FR-1.2: Live Registry Re-crawl for Selected Ecosystem
    with st.expander("🔄 Live Registry Re-crawl", expanded=False):
        eco_display = "PyPI" if "PyPI" in selected_ecosystem else "npm"
        st.markdown(
            f"<div style='font-size:0.8rem; color:#9bb3b8; margin-bottom:6px;'>"
            f"Query live <b>{eco_display}</b> registry API and refresh graph cache:"
            f"</div>",
            unsafe_allow_html=True
        )
        if st.button(f"Fetch Fresh {eco_display} Graph", key="live_fetch_btn"):
            with st.spinner(f"Crawling {eco_display} registry..."):
                if "PyPI" in selected_ecosystem:
                    get_cached_or_fetch_pypi_graph(force_refresh=True)
                else:
                    get_cached_or_fetch_graph(force_refresh=True)
                st.cache_data.clear()
                st.rerun()

    st.markdown("---")
    render_html(
        """
        <h4 style="color:#c8b6ff;">🎨 Graph Legend</h4>
        <div style="font-size:0.85rem; line-height:1.8; color:#e0e7e9;">
            <div><span style="color:#e63946; font-weight:bold;">●</span> Critical Risk (&ge; 70)</div>
            <div><span style="color:#f4a261; font-weight:bold;">●</span> High Risk (&ge; 45)</div>
            <div><span style="color:#b388eb; font-weight:bold;">●</span> Medium Risk (&ge; 25)</div>
            <div><span style="color:#005f73; font-weight:bold;">●</span> Low Risk (&lt; 25)</div>
            <div><span style="color:#0a9396; font-weight:bold;">◆</span> Top-Level Application Seed</div>
            <div><span style="color:#ff4d6d; font-weight:bold;">★</span> Compromised Origin(s)</div>
            <div><span style="color:#ffb703; font-weight:bold;">▲</span> Multi-Origin Overlap</div>
            <div><span style="color:#b388eb; font-weight:bold;">◇</span> Single-Origin Blast Radius</div>
            <div><span style="color:#ffd166; font-weight:bold;">🎲</span> Monte Carlo Shading (Opacity &prop; Probability)</div>
            <div><span style="color:#c8b6ff; font-weight:bold;">━</span> Propagation Attack Path</div>
        </div>
        """
    )

    st.markdown("---")
    snapshot_meta = raw_data.get("metadata", {})
    snapshot_id = snapshot_meta.get("snapshot_id", "rg-snap-default")
    schema_ver = snapshot_meta.get("schema_version", "1.0")
    source_type = snapshot_meta.get("source_type", "npm-crawl")
    render_html(
        f"""
        <div style="font-size:0.75rem; color:#78909c;">
            <b>Active Graph:</b><br/><code>{active_source_label}</code><br/>
            <b>Snapshot ID:</b><br/><code>{snapshot_id}</code><br/>
            <b>Source:</b> {source_type} • <b>Schema:</b> v{schema_ver}<br/><br/>
            <b>SDG 9 Alignment:</b> Promoting resilient digital infrastructure through transparent, explainable open-source supply chain verification.
        </div>
        """
    )

# ---------------------------------------------------------
# Dynamic Criticality Scoring (Recomputed with Active Weights)
# ---------------------------------------------------------
scores = {}
live_cvss_map = {}
if use_live_osv:
    pkg_queries = [
        (node, metrics[node].get("ecosystem", "npm"))
        for node in G.nodes()
    ]
    live_cvss_map = query_osv_batch(pkg_queries)

for node in G.nodes():
    live_cvss_val = None
    if use_live_osv:
        eco = "PyPI" if metrics[node].get("ecosystem", "npm").lower() in ["pypi", "python"] else "npm"
        live_cvss_val = live_cvss_map.get((node.strip().lower(), eco))
    scores[node] = compute_composite_criticality(
        node,
        metrics[node],
        max_in,
        max_trans,
        weight_config=active_weight_cfg,
        live_cvss=live_cvss_val,
        max_betweenness=max_bw
    )

# ---------------------------------------------------------
# Top Header Banner
# ---------------------------------------------------------
render_html(
    """
    <div class="header-box">
        <div class="header-title">
            <span>🛡️ RippleGuard</span>
        </div>
        <div class="header-subtitle">
            Explainable Dependency-Risk Intelligence & Blast-Radius Simulator
        </div>
        <div class="sdg-tag">
            🎯 SDG 9: Industry, Innovation & Infrastructure • Software Supply Chain Security
        </div>
    </div>
    """
)

# ---------------------------------------------------------
# Top KPI Metric Cards
# ---------------------------------------------------------
ranked_nodes = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
top_node, top_sc = ranked_nodes[0] if ranked_nodes else ("None", {"score": 0, "tier": "LOW"})

col1, col2, col3, col4 = st.columns(4)
with col1:
    render_html(
        f"""
        <div class="metric-card">
            <div class="metric-label">Analyzed Packages</div>
            <div class="metric-value">{G.number_of_nodes()}</div>
        </div>
        """
    )
with col2:
    render_html(
        f"""
        <div class="metric-card">
            <div class="metric-label">Dependency Links</div>
            <div class="metric-value">{G.number_of_edges()}</div>
        </div>
        """
    )
with col3:
    seed_count = len(raw_data.get("metadata", {}).get("seeds", []))
    render_html(
        f"""
        <div class="metric-card">
            <div class="metric-label">Seed Applications</div>
            <div class="metric-value">{seed_count}</div>
        </div>
        """
    )
with col4:
    render_html(
        f"""
        <div class="metric-card">
            <div class="metric-label">Top Criticality Target</div>
            <div class="metric-value" style="color:#ff6b6b; font-size:1.4rem; overflow:hidden; text-overflow:ellipsis;">
                {top_node} <span style="font-size:0.9rem; color:#aaa;">({top_sc['score']}/100)</span>
            </div>
        </div>
        """
    )

st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# Sticky In-Page Navigation Bar
# ---------------------------------------------------------
render_html(
    """
    <div class="nav-bar-container">
        <span class="nav-bar-label">Jump to:</span>
        <div class="nav-bar-links">
            <a href="#tutorial-section" onclick="const t = document.getElementById('tutorial-section'); if(t){t.scrollIntoView({behavior:'smooth'}); const det = t.closest('.stElementContainer')?.nextElementSibling?.querySelector('details'); if(det && !det.open) det.open = true;}" class="nav-link-btn">❓ How to Use</a>
            <a href="#graph-section" class="nav-link-btn">🕸️ Graph</a>
            <a href="#dossier-section" class="nav-link-btn">📦 Risk Dossier</a>
            <a href="#fix-section" class="nav-link-btn">🎯 Fix This First</a>
            <a href="#leaderboard-section" class="nav-link-btn">🏆 Leaderboard</a>
        </div>
    </div>
    """
)

# ---------------------------------------------------------
# SECTION 0: Tutorial & Onboarding Guide (Quick Start & SBOM Guide)
# ---------------------------------------------------------
render_html('<div id="tutorial-section" class="section-anchor"></div>')
with st.expander("❓ How to Use RippleGuard: Quick Start & Custom Project Guide", expanded=False):
    render_html(
        """
        <div style="padding: 4px 0 8px 0;">
            <div style="font-size: 1.1rem; font-weight: 700; color: #ffffff; margin-bottom: 6px;">
                🚀 Quick Start Guide
            </div>
            <div style="font-size: 0.88rem; color: #9bb3b8; margin-bottom: 16px;">
                Follow these four steps to analyze software supply chain vulnerability cascades and prioritize remediations:
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 20px;">
                <div style="background: rgba(0, 95, 115, 0.15); border: 1px solid #0a9396; border-radius: 8px; padding: 12px 14px;">
                    <div style="color: #0a9396; font-weight: 700; font-size: 0.85rem; margin-bottom: 4px;">1. EXPLORE GRAPH</div>
                    <div style="font-size: 0.84rem; color: #e0e7e9; line-height: 1.4;">
                        Pan, zoom, and inspect dependencies in the interactive graph below. Diamond nodes (◆) represent root application seeds.
                    </div>
                </div>
                <div style="background: rgba(179, 136, 235, 0.12); border: 1px solid #b388eb; border-radius: 8px; padding: 12px 14px;">
                    <div style="color: #c8b6ff; font-weight: 700; font-size: 0.85rem; margin-bottom: 4px;">2. SIMULATE ATTACK</div>
                    <div style="font-size: 0.84rem; color: #e0e7e9; line-height: 1.4;">
                        Select any package and click <b>Simulate</b> to trace how a compromise cascades upstream into your applications.
                    </div>
                </div>
                <div style="background: rgba(244, 162, 97, 0.12); border: 1px solid #f4a261; border-radius: 8px; padding: 12px 14px;">
                    <div style="color: #f4a261; font-weight: 700; font-size: 0.85rem; margin-bottom: 4px;">3. ANALYZE YOUR PROJECT</div>
                    <div style="font-size: 0.84rem; color: #e0e7e9; line-height: 1.4;">
                        Upload your own project's lockfile or SBOM in the sidebar to evaluate your team's real supply chain topology.
                    </div>
                </div>
                <div style="background: rgba(230, 57, 70, 0.12); border: 1px solid #e63946; border-radius: 8px; padding: 12px 14px;">
                    <div style="color: #ff6b6b; font-weight: 700; font-size: 0.85rem; margin-bottom: 4px;">4. FIX THIS FIRST</div>
                    <div style="font-size: 0.84rem; color: #e0e7e9; line-height: 1.4;">
                        Review consolidated remediations that neutralize multiple overlapping alerts at once to eliminate alert fatigue.
                    </div>
                </div>
            </div>

            <hr style="border: 0; border-top: 1px solid #15454d; margin: 18px 0;" />

            <div style="font-size: 1.1rem; font-weight: 700; color: #ffffff; margin-bottom: 6px;">
                📂 Analyze Your Own Project (Custom Manifest & SBOM Upload)
            </div>
            <div style="font-size: 0.88rem; color: #9bb3b8; margin-bottom: 14px;">
                RippleGuard enables you to move beyond sample graphs and audit your organization's actual production dependencies.
            </div>

            <div style="background: rgba(0, 0, 0, 0.25); border: 1px solid #1a3c42; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
                <div style="font-size: 0.95rem; font-weight: 700; color: #c8b6ff; margin-bottom: 8px;">
                    📄 Accepted File Formats & Where to Find Them
                </div>
                <ul style="font-size: 0.85rem; color: #e0e7e9; line-height: 1.6; margin: 0 0 8px 18px; padding: 0;">
                    <li><b>npm lockfile (<code>package-lock.json</code>)</b>: Supports formats v1, v2, and v3. Located in your project's root folder right next to <code>package.json</code> after running <code>npm install</code>.</li>
                    <li><b>CycloneDX SBOM (<code>*.json</code>)</b>: Industry-standard Software Bill of Materials (spec v1.4, v1.5, v1.6). Can be generated from any codebase using tools like <code>cdxgen -o bom.json</code> or Syft.</li>
                </ul>
            </div>

            <div style="background: rgba(0, 0, 0, 0.25); border: 1px solid #1a3c42; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
                <div style="font-size: 0.95rem; font-weight: 700; color: #c8b6ff; margin-bottom: 8px;">
                    ⚙️ Step-by-Step Upload Workflow
                </div>
                <ol style="font-size: 0.85rem; color: #e0e7e9; line-height: 1.6; margin: 0 0 8px 18px; padding: 0;">
                    <li>Open the left sidebar and expand the <b>"📂 Upload Manifest / SBOM"</b> panel.</li>
                    <li>Drag and drop or browse to select your <code>package-lock.json</code> or CycloneDX JSON file.</li>
                    <li>The engine automatically ingests the topology in milliseconds:
                        the graph rebuilds with your exact dependencies, the active source badge reflects your uploaded file, and all risk scores, blast radii, and prioritized fixes recalculate.
                    </li>
                    <li>To switch back to the demo dataset at any time, click the <b>"↺ Return to Demo Dataset"</b> button in the sidebar.</li>
                </ol>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
                <div style="background: rgba(10, 147, 150, 0.12); border: 1px solid #0a9396; border-radius: 8px; padding: 12px 16px;">
                    <div style="color: #0a9396; font-weight: 700; font-size: 0.88rem; margin-bottom: 4px;">
                        🛡️ 100% Offline & Private Analysis
                    </div>
                    <div style="font-size: 0.82rem; color: #e0e7e9; line-height: 1.45;">
                        Your uploaded files are processed entirely offline within your local session memory. <b>No proprietary code, private package names, or internal manifests are transmitted to external servers or third parties.</b>
                    </div>
                </div>
                <div style="background: rgba(200, 182, 255, 0.1); border: 1px solid rgba(200, 182, 255, 0.3); border-radius: 8px; padding: 12px 16px;">
                    <div style="color: #c8b6ff; font-weight: 700; font-size: 0.88rem; margin-bottom: 4px;">
                        ⚠️ Graceful Error Handling
                    </div>
                    <div style="font-size: 0.82rem; color: #e0e7e9; line-height: 1.45;">
                        If an uploaded file is invalid or corrupted, RippleGuard safely halts parsing, displays a clean user-facing error message, and retains the active demo graph without crashing.
                    </div>
                </div>
            </div>

            <hr style="border: 0; border-top: 1px solid #15454d; margin: 18px 0;" />

            <div style="font-size: 1.1rem; font-weight: 700; color: #ffffff; margin-bottom: 6px;">
                📖 Essential Risk Glossary
            </div>
            <div style="font-size: 0.85rem; color: #9bb3b8; margin-bottom: 12px;">
                Key concepts used across RippleGuard's analytics:
            </div>
            <div style="font-size: 0.84rem; color: #e0e7e9; line-height: 1.6;">
                <div style="margin-bottom: 6px;">
                    • <b style="color:#c8b6ff;">Criticality Score (0–100):</b> A composite index combining a package's baseline CVE vulnerability severity with its topological reach and bottleneck position in your dependency network. <i>(Inspect "Show Raw Reasoning" in the Package Dossier for the complete mathematical breakdown.)</i>
                </div>
                <div style="margin-bottom: 6px;">
                    • <b style="color:#ff6b6b;">Blast Radius:</b> The total number of downstream packages and root application seeds compromised if this specific dependency is attacked or sabotaged.
                </div>
                <div style="margin-bottom: 6px;">
                    • <b style="color:#ffd166;">Hidden Critical:</b> A foundational dependency with a low or modest individual CVE score that nevertheless poses critical risk because numerous higher-level packages depend on it.
                </div>
                <div style="margin-bottom: 6px;">
                    • <b style="color:#2a9d8f;">Deterministic vs. Monte Carlo:</b> Deterministic mode calculates the theoretical worst-case cascade (assuming 100% path breach); Monte Carlo simulates 1,000 stochastic trials factoring in lockfile pinning to estimate realistic infection likelihoods.
                </div>
                <div style="margin-bottom: 4px;">
                    • <b style="color:#c8b6ff;">Fix This First (Coverage vs. Efficiency):</b> A greedy set-cover remediation planner that finds the minimum package upgrades required to eliminate overlapping attack paths. Switch between <i>Efficiency</i> (highest ROI per effort tier) and <i>Coverage</i> (maximum absolute risk reduction).
                </div>
            </div>
        </div>
        """
    )

# ---------------------------------------------------------
# Simulation Computation (if active) -- FR-4.3 BFS / FR-4.4 Monte Carlo
# ---------------------------------------------------------
active_sim = None
mc_result = None
comp_targets = st.session_state.compromised_nodes if st.session_state.compromised_nodes else (
    [st.session_state.compromised_node] if st.session_state.compromised_node else []
)

if comp_targets:
    if use_monte_carlo:
        n_trials_val = st.session_state.get("mc_n_trials", 1000)
        mc_result = simulate_monte_carlo(G, comp_targets, n_trials=n_trials_val, seed=42)
        active_sim = mc_result.deterministic_result  # BFS result for graph structure
    else:
        active_sim = simulate_compromise(G, comp_targets)

# ---------------------------------------------------------
# SECTION 1: Full-Width Interactive Dependency Graph
# ---------------------------------------------------------
render_html('<div id="graph-section" class="section-anchor"></div>')

graph_header_title = "Interactive Dependency Graph"
if active_sim:
    origins = active_sim.get("compromised_nodes", [active_sim["compromised_node"]])
    if mc_result:
        if len(origins) > 1:
            graph_header_title = f"🎲 Monte Carlo Blast Radius ({len(origins)} Origins, N={mc_result.n_trials}): `{', '.join(origins)}`"
        else:
            graph_header_title = f"🎲 Monte Carlo Blast Radius (N={mc_result.n_trials}): `{active_sim['compromised_node']}`"
    else:
        if len(origins) > 1:
            graph_header_title = f"💥 Multi-Origin Blast Radius ({len(origins)} Origins): `{', '.join(origins)}`"
        else:
            graph_header_title = f"💥 Blast Radius: Compromise Propagation from `{active_sim['compromised_node']}`"

render_html(
    f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <span style="font-size:1.15rem; font-weight:700; color:#c8b6ff;">
            {graph_header_title}
        </span>
        <span style="font-size:0.8rem; color:#9bb3b8;">
            Scroll to zoom • Drag to explore • Hover node for metadata
        </span>
    </div>
    """
)

with st.spinner("⚡ Rendering interactive force-directed graph..."):
    pyvis_html = create_pyvis_graph(
        G=G,
        metrics=metrics,
        scores=scores,
        selected_node=st.session_state.selected_package,
        simulation_result=active_sim,
        mc_probabilities=mc_result.infection_probability if mc_result else None,
        height="580px"
    )
    components.html(pyvis_html, height=590, scrolling=False)

# ---------------------------------------------------------
# SECTION 2: Balanced Two-Column Details (Dossier & Remediation)
# ---------------------------------------------------------
# Precompute active fix report for both detail columns
active_fix_strat = "cost_impact" if "efficiency" in st.session_state.get("ui_fix_ranking_strategy", "efficiency").lower() else "coverage_only"
active_fix_report = consolidate_fixes(G, scores, metrics, ranking_strategy=active_fix_strat)

st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
left_detail_col, right_detail_col = st.columns([1, 1], gap="large")

# --- LEFT DETAIL COLUMN: Package Risk Dossier & Diagnostic Details ---
with left_detail_col:
    render_html('<div id="dossier-section" class="section-anchor"></div>')
    curr_pkg = st.session_state.selected_package
    curr_metrics = metrics.get(curr_pkg, {})
    curr_score_data = scores.get(curr_pkg, {"score": 0, "tier": "LOW", "cvss": 1.0, "is_curated_cve": False, "is_hidden_critical": False})
    tier = curr_score_data["tier"]
    if curr_score_data.get("severity_source") == "live_osv":
        cvss_badge_text = f"Base CVSS: {curr_score_data['cvss']}/10 (Live OSV.dev)"
    elif curr_score_data.get("is_curated_cve"):
        cvss_badge_text = f"Base CVSS: {curr_score_data['cvss']}/10 (Curated CVE)"
    else:
        cvss_badge_text = f"Base CVSS: {curr_score_data['cvss']}/10 (Default Baseline)"
    conf_label = "High confidence (curated/live data)" if curr_score_data.get("severity_source") in ["curated", "live_osv"] else "Estimated (default baseline)"

    # If simulation is active, show the blast-radius alert box
    if active_sim:
        aff_count = active_sim["affected_count"]
        aff_seeds = active_sim["affected_seeds"]
        max_hops = active_sim["max_hops"]
        multi_origins = active_sim.get("multi_origin_nodes", [])
        origins = active_sim.get("compromised_nodes", [active_sim["compromised_node"]])
        is_multi = len(origins) > 1
        is_contained = (not is_multi and curr_metrics.get("transitive_dependents_count", 0) == 0)

        if is_contained:
            render_html(
                f"""
                <div class="blast-alert" style="background: rgba(0, 95, 115, 0.3); border-color: #0a9396;">
                    <div style="font-size:1.1rem; font-weight:800; color:#ffffff; margin-bottom:4px;">
                        🛡️ Zero-Downstream Root Application
                    </div>
                    <div style="font-size:0.9rem; color:#f0f7f8;">
                        Compromising <b>`{active_sim['compromised_node']}`</b> is <b>completely contained</b>:
                        it is a top-level application root with no upstream dependents in this graph (0 transitive hops).
                    </div>
                </div>
                """
            )
        else:
            multi_badge_html = ""
            if is_multi:
                alert_title = f"🚨 Multi-Origin Compromise Active ({len(origins)} Origins Simulated)"
                origin_list_html = ", ".join(f"<b>`{o}`</b>" for o in origins)
                if multi_origins:
                    multi_badge_html = f"""
                    <div style="margin-top:8px; padding:6px 10px; background:rgba(255, 183, 3, 0.18); border:1px solid #ffb703; border-radius:6px; font-size:0.85rem; color:#ffd166;">
                        ⚡ <b>Overlapping Blast Radius ({len(multi_origins)} packages):</b> {', '.join([f'<code>{m}</code>' for m in multi_origins[:6]])}{'...' if len(multi_origins) > 6 else ''}
                    </div>
                    """
            else:
                alert_title = "🚨 Compromise Simulation Active"
                origin_list_html = f"<b>`{active_sim['compromised_node']}`</b>"

            render_html(
                f"""
                <div class="blast-alert">
                    <div style="font-size:1.1rem; font-weight:800; color:#ffffff; margin-bottom:4px;">
                        {alert_title}
                    </div>
                    <div style="font-size:0.9rem; color:#f0f7f8;">
                        Compromising {origin_list_html} propagates across <b>{aff_count} packages</b> 
                        within <b>{max_hops} hop(s)</b>, directly threatening <b>{len(aff_seeds)} top-level application seeds</b>!
                    </div>
                    {multi_badge_html}
                </div>
                """
            )

        with st.expander("🔗 Attack Propagation Tree & Paths to Seeds", expanded=True):
            if is_contained:
                st.info(f"Target `{curr_pkg}` is a root application seed. No other applications or packages depend on it.")
            else:
                if multi_origins:
                    st.markdown(f"<b style='color:#ffd166;'>⚡ Multi-Origin Blast Overlap ({len(multi_origins)} packages):</b>", unsafe_allow_html=True)
                    for m in multi_origins:
                        reaches = active_sim.get("origin_reachability", {}).get(m, {})
                        reach_desc = " and ".join([f"<b>`{orig}`</b> ({d} hop{'s' if d != 1 else ''})" for orig, d in reaches.items()])
                        path_nodes = active_sim["propagation_paths"].get(m, [m])
                        path_str = " ➔ ".join([f"`{p}`" for p in path_nodes])
                        st.markdown(f"- **`{m}`**: reached via {reach_desc} (shortest path: {path_str})")
                    st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)

                if aff_seeds:
                    st.markdown("<b style='color:#c8b6ff;'>Propagation Paths to Seeds:</b>", unsafe_allow_html=True)
                    for s in aff_seeds:
                        path_nodes = active_sim["propagation_paths"].get(s, [s])
                        path_str = " ➔ ".join([f"`{p}`" for p in path_nodes])
                        reaches = active_sim.get("origin_reachability", {}).get(s, {})
                        via_info = ""
                        if len(reaches) > 1:
                            via_info = " *(reached via " + ", ".join([f"`{o}`" for o in reaches.keys()]) + ")*"
                        st.markdown(f"- **`{s}`**: {path_str}{via_info}")
                else:
                    st.info("No top-level application seeds directly reached from this node.")

                st.markdown("<b style='color:#c8b6ff; margin-top:8px;'>Infection Stages by Hop Distance:</b>", unsafe_allow_html=True)
                for hop, pkgs in sorted(active_sim["levels"].items()):
                    if hop == 0:
                        hop_label = f"Compromised Origin(s) ({len(pkgs)})"
                    else:
                        hop_label = f"Hop {hop} Downstream ({len(pkgs)})"
                    st.markdown(f"**{hop_label}:** " + ", ".join([f"`{p}`" for p in pkgs[:6]]) + ("..." if len(pkgs) > 6 else ""))

        # FR-4.4: Monte Carlo probability panel
        if mc_result and not is_contained:
            with st.expander("🎲 Monte Carlo: Per-Node Infection Probability", expanded=True):
                st.caption(
                    f"**{mc_result.n_trials:,} trials** completed in **{mc_result.elapsed_ms:.1f} ms** · "
                    f"Mean infection probability: **{mc_result.confidence:.1%}** across affected nodes · "
                    f"Edge probabilities derived from version pin status — **disclosed heuristic estimate, not measured data**."
                )

                # Build probability table sorted by probability descending
                mc_rows = []
                for n in active_sim.get("affected_nodes", []):
                    p = mc_result.infection_probability.get(n, 0.0)
                    std = mc_result.infection_std.get(n, 0.0)
                    is_partial = n in mc_result.partial_propagation_nodes
                    is_origin = n in mc_result.compromised_nodes
                    mc_rows.append((n, p, std, is_partial, is_origin))
                mc_rows.sort(key=lambda x: -x[1])

                for pkg_name, p, std, is_partial, is_origin in mc_rows:
                    bar_pct = int(p * 100)
                    if is_origin:
                        tag = "<span style='color:#ff4d6d; font-size:0.75rem;'>★ origin</span>"
                        bar_color = "#ff4d6d"
                    elif p >= 0.95:
                        tag = "<span style='color:#f4a261; font-size:0.75rem;'>≈ certain</span>"
                        bar_color = "#b388eb"
                    elif is_partial:
                        tag = "<span style='color:#ffd166; font-size:0.75rem;'>⚡ partial</span>"
                        bar_color = "#ffd166"
                    else:
                        tag = ""
                        bar_color = "#78909c"
                    st.markdown(
                        f"<div style='margin-bottom:4px;'>"
                        f"<span style='font-size:0.85rem; color:#e0e7e9; font-family:monospace;'>{pkg_name}</span> "
                        f"<span style='color:{bar_color}; font-weight:700;'>{bar_pct}%</span> "
                        f"<span style='font-size:0.75rem; color:#9bb3b8;'>±{std:.3f}</span> {tag}"
                        f"<div style='height:4px; width:{bar_pct}%; background:{bar_color}; border-radius:2px; opacity:0.7; margin-top:2px;'></div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                if mc_result.partial_propagation_nodes:
                    st.markdown(
                        f"<div style='margin-top:8px; font-size:0.8rem; color:#ffd166;'>"
                        f"⚡ <b>{len(mc_result.partial_propagation_nodes)} partial-propagation node(s)</b>: "
                        f"BFS says 'affected' but MC probability &lt; 95% — "
                        f"{', '.join([f'<code>{n}</code>' for n in mc_result.partial_propagation_nodes[:6]])}"
                        f"{'...' if len(mc_result.partial_propagation_nodes) > 6 else ''}"
                        f"</div>",
                        unsafe_allow_html=True
                    )

    # --- Node Overview & Explainability Card ---
    hidden_critical_badge = ""
    if curr_score_data.get("is_hidden_critical"):
        hidden_critical_badge = '<div style="margin-bottom:10px;"><span style="background:rgba(230, 57, 70, 0.2); color:#ff6b6b; border:1px solid #e63946; padding:3px 10px; border-radius:6px; font-weight:700; font-size:0.82rem;">⚠️ HIDDEN CRITICAL: Blast Radius Amplification</span></div>'

    mc_dossier_badge = ""
    mc_grid_card = ""
    if mc_result and curr_pkg in mc_result.infection_probability:
        p_val = mc_result.infection_probability[curr_pkg]
        std_val = mc_result.infection_std.get(curr_pkg, 0.0)
        is_partial = curr_pkg in mc_result.partial_propagation_nodes
        status_txt = "Partial Propagation" if is_partial else ("Compromised Origin" if curr_pkg in mc_result.compromised_nodes else "High Likelihood")
        mc_dossier_badge = f'<span style="font-size:0.82rem; color:#ffd166; background:rgba(255,183,3,0.15); border:1px solid #ffb703; padding:2px 8px; border-radius:4px;">🎲 MC Prob: {p_val:.1%} (±{std_val:.3f})</span>'
        mc_grid_card = f'<div style="margin-top:10px; background:rgba(255,183,3,0.08); padding:8px 12px; border-radius:6px; border:1px solid rgba(255,183,3,0.3);"><div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-size:0.75rem; color:#ffd166; text-transform:uppercase; font-weight:700;">🎲 Monte Carlo Infection Likelihood</span><span style="font-size:0.75rem; color:#9bb3b8;">{mc_result.n_trials} trials · {status_txt}</span></div><div style="font-size:1.3rem; font-weight:700; color:#ffd166; margin-top:2px;">{p_val:.1%} <span style="font-size:0.8rem; font-weight:normal; color:#9bb3b8;">(std dev ±{std_val:.3f})</span></div></div>'

    license_badge = f'<span style="font-size:0.82rem; color:#9bb3b8; background:rgba(255,255,255,0.05); padding:2px 8px; border-radius:4px;">License: {curr_metrics.get("license")}</span>' if curr_metrics.get("license") else ""
    published_badge = f'<span style="font-size:0.82rem; color:#9bb3b8; background:rgba(255,255,255,0.05); padding:2px 8px; border-radius:4px;">Published: {str(curr_metrics.get("publish_date"))[:10]}</span>' if curr_metrics.get("publish_date") else ""
    expl_text = generate_explanation(curr_pkg, curr_score_data, curr_metrics)

    dossier_html = (
        f'<div class="panel-card">'
        f'<div class="panel-title"><span>📦 Package Risk Dossier: <b>{curr_pkg}</b></span></div>'
        f'{hidden_critical_badge}'
        f'<div style="display:flex; gap:10px; align-items:center; margin-bottom:14px; flex-wrap:wrap;">'
        f'<span class="badge-{tier.lower()}">{tier} RISK • {curr_score_data["score"]}/100</span>'
        f'<span style="font-size:0.82rem; color:#9bb3b8; background:rgba(255,255,255,0.05); padding:2px 8px; border-radius:4px;">{cvss_badge_text}</span>'
        f'<span style="font-size:0.82rem; color:{"#a7c957" if "High" in conf_label else "#e0a96d"}; background:rgba(255,255,255,0.05); padding:2px 8px; border-radius:4px; border:1px solid {"rgba(167,201,87,0.3)" if "High" in conf_label else "rgba(224,169,109,0.3)"};">{conf_label}</span>'
        f'{mc_dossier_badge}'
        f'<span style="font-size:0.82rem; color:#9bb3b8;">v{curr_metrics.get("version", "")}</span>'
        f'{license_badge}'
        f'{published_badge}'
        f'</div>'
        f'<div style="background:rgba(0,0,0,0.25); border-left:3px solid var(--lavender-vibrant); padding:10px 14px; border-radius:4px; font-size:0.92rem; line-height:1.55; color:#e0e7e9; margin-bottom:14px;">{expl_text}</div>'
        f'<div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">'
        f'<div style="background:rgba(0,0,0,0.2); padding:8px 12px; border-radius:6px; border:1px solid #14373d;"><div style="font-size:0.75rem; color:#9bb3b8; text-transform:uppercase;">Direct Dependents</div><div style="font-size:1.3rem; font-weight:700; color:#c8b6ff;">{curr_metrics.get("in_degree", 0)}</div></div>'
        f'<div style="background:rgba(0,0,0,0.2); padding:8px 12px; border-radius:6px; border:1px solid #14373d;"><div style="font-size:0.75rem; color:#9bb3b8; text-transform:uppercase;">Transitive Blast Radius</div><div style="font-size:1.3rem; font-weight:700; color:#ff6b6b;">{curr_metrics.get("transitive_dependents_count", 0)} pkgs</div></div>'
        f'</div>'
        f'{mc_grid_card}'
        f'</div>'
    )
    render_html(dossier_html)

    # FR-5.4: Auditor Drill-Down: Show Raw Reasoning Expander
    w_cfg = curr_score_data.get("weighting_config", active_weight_cfg)
    w_c = w_cfg.weight_cvss
    w_t = w_cfg.weight_transitive
    w_i = w_cfg.weight_indegree
    w_b = getattr(w_cfg, "weight_betweenness", 0.0)
    n_cvss = curr_score_data.get("norm_cvss", 0.0)
    n_trans = curr_score_data.get("norm_trans", 0.0)
    n_indeg = curr_score_data.get("norm_in_deg", 0.0)
    n_between = curr_score_data.get("norm_between", curr_score_data.get("norm_betweenness", 0.0))
    bw_val = curr_metrics.get("betweenness_centrality", 0.0)
    v_sub = curr_score_data.get("vulnerability_subscore", 0.0)
    s_sub = curr_score_data.get("structural_subscore", 0.0)
    c_score = curr_score_data.get("composite_score", curr_score_data.get("score", 0.0))

    formula_str = "<code>score = (w_cvss × norm_cvss) + (w_trans × norm_trans) + (w_indeg × norm_in_deg)</code>"
    subst_str = f"<code>{c_score:.1f} = ({w_c:.2f} × {n_cvss:.1f}) + ({w_t:.2f} × {n_trans:.1f}) + ({w_i:.2f} × {n_indeg:.1f})</code>"
    if w_b > 0:
        formula_str = "<code>score = (w_cvss × norm_cvss) + (w_trans × norm_trans) + (w_indeg × norm_in_deg) + (w_between × norm_between)</code>"
        subst_str = f"<code>{c_score:.1f} = ({w_c:.2f} × {n_cvss:.1f}) + ({w_t:.2f} × {n_trans:.1f}) + ({w_i:.2f} × {n_indeg:.1f}) + ({w_b:.2f} × {n_between:.1f})</code>"

    with st.expander("🔍 Show Raw Reasoning (Auditor Drill-Down)", expanded=False):
        render_html(
            f"""
            <div style="font-size:0.85rem; line-height:1.6; color:#e0e7e9;">
                <b>Raw Scoring Formula:</b><br/>
                {formula_str}<br/><br/>
                <b>Substituted Computation for <code>{curr_pkg}</code>:</b><br/>
                {subst_str}<br/>
                <code>{c_score:.1f} = {v_sub:.1f} (vulnerability) + {s_sub:.1f} (structural)</code><br/><br/>
                <b>Component Subscores:</b><br/>
                • <b>Vulnerability Subscore:</b> <code>{v_sub:.1f}</code> (normalized CVSS: <code>{n_cvss:.1f}</code>)<br/>
                • <b>Structural Subscore:</b> <code>{s_sub:.1f}</code> (transitive reach: <code>{n_trans:.1f}</code>, in-degree: <code>{n_indeg:.1f}</code>, betweenness: <code>{n_between:.1f}</code>)<br/><br/>
                <b>Active Weighting Configuration:</b><br/>
                • <code>w_cvss</code>: {w_c:.2f} ({int(round(w_c*100))}%)<br/>
                • <code>w_trans</code>: {w_t:.2f} ({int(round(w_t*100))}%)<br/>
                • <code>w_indeg</code>: {w_i:.2f} ({int(round(w_i*100))}%)<br/>
                • <code>w_between</code>: {w_b:.2f} ({int(round(w_b*100))}%)<br/><br/>
                <b>Normalized Inputs:</b><br/>
                • <code>norm_cvss</code>: {n_cvss:.1f}% (Base CVSS {curr_score_data['cvss']}/10.0)<br/>
                • <code>norm_trans</code>: {n_trans:.1f}% ({curr_metrics.get('transitive_dependents_count', 0)} / {max_trans} max transitive)<br/>
                • <code>norm_in_deg</code>: {n_indeg:.1f}% ({curr_metrics.get('in_degree', 0)} / {max_in} max in-degree)<br/>
                • <code>norm_between</code>: {n_between:.1f}% (Betweenness Centrality: {bw_val:.6f})
            </div>
            """
        )

    # --- Mitigation Recommendations ---
    mitigations = get_mitigations_for_tier(tier)
    with st.expander("🛠️ Recommended Supply Chain Mitigations", expanded=False):
        st.markdown(
            f"<div style='font-size:0.85rem; color:#9bb3b8; margin-bottom:8px;'>Actionable safeguards tailored for <b>{tier}</b> structural risk:</div>",
            unsafe_allow_html=True
        )
        for mit in mitigations:
            st.markdown(f"• {mit}")

    # FR-6.5: Export Scenario Report (Markdown Download) reflecting active simulation & fix ranking
    report_markdown = generate_scenario_report(
        package_name=curr_pkg,
        score_data=curr_score_data,
        metrics=curr_metrics,
        explanation=generate_explanation(curr_pkg, curr_score_data, curr_metrics),
        ecosystem=curr_metrics.get("ecosystem", "npm"),
        active_source_label=active_source_label,
        snapshot_id=raw_data.get("metadata", {}).get("snapshot_id"),
        simulation_result=active_sim,
        fix_report=active_fix_report,
        mc_result=mc_result
    )
    st.download_button(
        label="📄 Export Report (Markdown)",
        data=report_markdown,
        file_name=f"rippleguard-report-{curr_pkg}.md",
        mime="text/markdown",
        use_container_width=True,
        help="Download an explainable Markdown audit report reflecting active simulation and remediation rankings."
    )

# --- RIGHT DETAIL COLUMN: Consolidated Remediation Priorities ("Fix This First") ---
with right_detail_col:
    render_html('<div id="fix-section" class="section-anchor"></div>')
    with st.expander("🎯 Fix This First: Consolidated Remediation Priorities", expanded=True):
        fix_strat_col1, fix_strat_col2 = st.columns([3, 2])
        with fix_strat_col1:
            fix_strategy_ui = st.radio(
                "Remediation Ranking Strategy:",
                options=["Rank by efficiency (coverage per effort)", "Rank by coverage"],
                index=0,
                horizontal=True,
                key="ui_fix_ranking_strategy",
                help="Rank remediations by efficiency (marginal risk coverage divided by effort cost) or purely by total risk coverage alone."
            )
        active_strategy = "cost_impact" if "efficiency" in fix_strategy_ui.lower() else "coverage_only"

        with fix_strat_col2:
            strat_desc = "⚡ <b>Efficiency View:</b> Prioritizing high ROI (biggest bang for least effort)" if active_strategy == "cost_impact" else "📊 <b>Coverage View:</b> Prioritizing absolute blast radius coverage regardless of effort"
            st.markdown(f"<div style='font-size:0.78rem; color:#9bb3b8; margin-top:28px;'>{strat_desc}</div>", unsafe_allow_html=True)

        render_html(
            f"""
            <div style="background:linear-gradient(135deg, rgba(0, 95, 115, 0.25) 0%, rgba(179, 136, 235, 0.2) 100%); border:1px solid #0a9396; border-radius:8px; padding:12px 16px; margin-bottom:12px;">
                <div style="font-size:1.05rem; font-weight:800; color:#ffffff; margin-bottom:4px;">
                    🎯 {active_fix_report.headline_stat}
                </div>
                <div style="font-size:0.82rem; color:#c8b6ff;">
                    Instead of triaging every alert individually, fix the foundational dependencies that eliminate the most overlapping risk at once (combats Dependabot alert fatigue).
                </div>
            </div>
            """
        )

        if active_fix_report.recommended_fixes:
            for fix in active_fix_report.recommended_fixes:
                subsumed_badge = ""
                if fix.subsumed_flagged_packages:
                    sub_names = ", ".join(fix.subsumed_flagged_packages)
                    subsumed_badge = f"<span style='background:rgba(200, 182, 255, 0.15); color:#e7c6ff; border:1px solid #b388eb; padding:2px 7px; border-radius:4px; font-size:0.75rem; font-weight:600; margin-left:6px;'>Blocks Path Via: {sub_names}</span>"

                tier_badge_col = "#e63946" if fix.tier == "CRITICAL" else "#f4a261"

                # FR-5.2: Effort styling badge
                eff_upper = (fix.effort_tier or "Medium").upper()
                if "LOW-MEDIUM" in eff_upper:
                    eff_badge = "<span style='background:rgba(233, 196, 106, 0.2); color:#e9c46a; border:1px solid #e9c46a; padding:2px 7px; border-radius:4px; font-size:0.75rem; font-weight:700;'>🟡 Low-Medium Effort</span>"
                elif "LOW" in eff_upper:
                    eff_badge = "<span style='background:rgba(42, 157, 143, 0.2); color:#2a9d8f; border:1px solid #2a9d8f; padding:2px 7px; border-radius:4px; font-size:0.75rem; font-weight:700;'>🟢 Low Effort</span>"
                elif "VERY HIGH" in eff_upper:
                    eff_badge = "<span style='background:rgba(180, 50, 50, 0.25); color:#ff6b6b; border:1px solid #ff4d6d; padding:2px 7px; border-radius:4px; font-size:0.75rem; font-weight:700;'>🟣 Very High Effort</span>"
                elif "HIGH" in eff_upper:
                    eff_badge = "<span style='background:rgba(230, 57, 70, 0.2); color:#e63946; border:1px solid #e63946; padding:2px 7px; border-radius:4px; font-size:0.75rem; font-weight:700;'>🔴 High Effort</span>"
                else:
                    eff_badge = "<span style='background:rgba(233, 196, 106, 0.2); color:#e9c46a; border:1px solid #e9c46a; padding:2px 7px; border-radius:4px; font-size:0.75rem; font-weight:700;'>🟡 Medium Effort</span>"

                roi_badge = f"<span style='background:rgba(179, 136, 235, 0.15); color:#c8b6ff; border:1px solid #b388eb; padding:2px 7px; border-radius:4px; font-size:0.75rem; font-weight:700; margin-left:6px;'>⚡ ROI: {fix.cost_impact_ratio:.1f}</span>"

                render_html(
                    f"""
                    <div class="priority-fix-card">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap;">
                            <div>
                                <b style="color:#c8b6ff; font-size:0.95rem;">#{fix.rank} Priority Fix: <code>{fix.package}</code></b>
                                <span style="color:{tier_badge_col}; font-weight:700; font-size:0.8rem; margin-left:8px;">[{fix.tier} • {fix.composite_score}/100]</span>
                                {subsumed_badge}
                            </div>
                            <div style="display:flex; align-items:center; gap:8px;">
                                {eff_badge}
                                {roi_badge}
                                <span style="color:#0a9396; font-weight:700; font-size:0.85rem; margin-left:4px;">
                                    {fix.cumulative_coverage_pct}% Cumulative Risk (+{fix.newly_covered_count})
                                </span>
                            </div>
                        </div>
                        <div style="font-size:0.78rem; color:#9bb3b8; margin-top:2px; margin-bottom:6px;">
                            Action: <span style="color:#e0e7e9; font-weight:600;">{fix.action_type}</span>
                        </div>
                        <div style="font-size:0.84rem; color:#e0e7e9; line-height:1.5;">
                            {fix.explanation}
                        </div>
                    </div>
                    """
                )
        else:
            st.info("No packages currently meet the alert threshold.")

# ---------------------------------------------------------
# SECTION 3: Full-Width Dependency Risk & Criticality Leaderboard
# ---------------------------------------------------------
st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
render_html('<div id="leaderboard-section" class="section-anchor"></div>')

with st.expander("🏆 Dependency Risk & Criticality Leaderboard", expanded=True):
    st.markdown("<div style='font-size:0.82rem; color:#9bb3b8; margin-bottom:8px;'>Interactive filtering and multi-attribute sorting across the dependency graph:</div>", unsafe_allow_html=True)

    lb_col1, lb_col2, lb_col3 = st.columns([5, 4, 3])
    with lb_col1:
        tier_filter = st.multiselect(
            "Filter Risk Tier:",
            options=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            default=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            key="lb_tier_filter"
        )
    with lb_col2:
        sort_metric = st.selectbox(
            "Sort By:",
            options=["Composite Score", "Transitive Blast Radius", "Direct In-Degree", "Base CVSS"],
            index=0,
            key="lb_sort_metric"
        )
    with lb_col3:
        st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
        hidden_only = st.checkbox("⚠️ Hidden Critical", value=False, key="lb_hidden_only", help="Filter for packages with modest CVSS whose structural reach amplifies them into HIGH/CRITICAL.")

    table_rows = []
    for node, sc in scores.items():
        m = metrics[node]
        if sc["tier"] not in tier_filter:
            continue
        if hidden_only and not sc.get("is_hidden_critical"):
            continue

        table_rows.append({
            "Rank": "",
            "Package": node,
            "Score": float(sc["score"]),
            "Tier": sc["tier"],
            "Hidden Critical": "⚠️ Yes" if sc.get("is_hidden_critical") else "No",
            "Blast Radius": int(m["transitive_dependents_count"]),
            "Direct Dependents": int(m["in_degree"]),
            "Base CVSS": float(sc["cvss"]),
            "Exposed Seeds": len(m["affected_seeds"])
        })

    sort_key_map = {
        "Composite Score": "Score",
        "Transitive Blast Radius": "Blast Radius",
        "Direct In-Degree": "Direct Dependents",
        "Base CVSS": "Base CVSS"
    }
    active_sort_key = sort_key_map.get(sort_metric, "Score")
    table_rows = sorted(table_rows, key=lambda x: x[active_sort_key], reverse=True)

    for rank, r in enumerate(table_rows, 1):
        r["Rank"] = f"#{rank}"

    if table_rows:
        st.dataframe(
            table_rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Rank": st.column_config.TextColumn("Rank", width="small", help="Criticality ranking across active graph"),
                "Package": st.column_config.TextColumn("Package", width="medium", help="Dependency package identifier"),
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.1f", width="medium", help="Composite Criticality Score (0-100)"),
                "Tier": st.column_config.TextColumn("Risk Tier", width="medium", help="Risk classification: CRITICAL (≥70), HIGH (50-69), MEDIUM (30-49), LOW (<30)"),
                "Hidden Critical": st.column_config.TextColumn("Hidden Crit", width="small", help="Amplified by structural reach despite modest vulnerability score"),
                "Blast Radius": st.column_config.NumberColumn("Blast Radius", format="%d pkgs", width="small", help="Total transitive dependents reaching this package"),
                "Direct Dependents": st.column_config.NumberColumn("In-Degree", format="%d", width="small", help="Direct incoming dependency edges"),
                "Base CVSS": st.column_config.NumberColumn("CVSS", format="%.1f", width="small", help="Base CVSS vulnerability severity score"),
                "Exposed Seeds": st.column_config.NumberColumn("Seeds", format="%d", width="small", help="Count of top-level application seeds directly exposed")
            }
        )
    else:
        st.info("No packages match the current filter criteria.")
