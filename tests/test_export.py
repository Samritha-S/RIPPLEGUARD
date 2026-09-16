"""
test_export.py - Tests for FR-6.5: Export scenario audit report.
Verifies Markdown generation, disclosures, scores, structural metrics,
compromise simulation propagation paths, and Fix Consolidation sections.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetcher import load_cached_graph, load_cached_pypi_graph
from src.graph_builder import build_dependency_graph, compute_structural_metrics
from src.scoring import compute_composite_criticality, generate_explanation
from src.simulator import simulate_compromise
from src.fix_consolidator import consolidate_fixes
from src.exporter import generate_scenario_report


def test_export_report_debug_baseline():
    """Verify Markdown report generation for 'debug' without active simulation."""
    data = load_cached_graph()
    G = build_dependency_graph(data)
    metrics = compute_structural_metrics(G)
    max_in = max(m["in_degree"] for m in metrics.values())
    max_trans = max(m["transitive_dependents_count"] for m in metrics.values())

    debug_metrics = metrics["debug"]
    debug_score = compute_composite_criticality("debug", debug_metrics, max_in, max_trans)
    explanation = generate_explanation("debug", debug_score, debug_metrics)
    fix_report = consolidate_fixes(G, {n: compute_composite_criticality(n, metrics[n], max_in, max_trans) for n in G.nodes()}, metrics)

    report_md = generate_scenario_report(
        package_name="debug",
        score_data=debug_score,
        metrics=debug_metrics,
        explanation=explanation,
        ecosystem="npm",
        active_source_label="Demo dataset (5 npm seeds)",
        snapshot_id=data.get("metadata", {}).get("snapshot_id"),
        simulation_result=None,
        fix_report=fix_report
    )

    # Core headers and package identity
    assert "# 🛡️ RippleGuard Scenario Audit Report: `debug`" in report_md
    assert "| **Package Name** | `debug` |" in report_md
    assert "| **Composite Criticality Score** | **79.5 / 100** |" in report_md
    assert "| **Assigned Risk Tier** | **CRITICAL RISK** |" in report_md
    assert "| **Base Severity (CVSS)** | **5.3 / 10.0** (Curated CVE Profile) |" in report_md
    assert "| **Direct Dependents (In-Degree)** | **7** packages |" in report_md
    assert "| **Transitive Blast Radius** | **9** downstream packages |" in report_md
    assert "| **Confidence Assessment (FR-5.5)** | **High confidence (curated/live data)** |" in report_md

    # Transparency Disclosures
    assert "- **Ecosystem:** `npm`" in report_md
    assert "- **Active Graph Source:** `Demo dataset (5 npm seeds)`" in report_md
    assert "Supply Chain Severity Caveat" in report_md
    assert "Curated CVE Profile" in report_md

    # Plain-language explanation
    assert "structural amplification" in report_md
    assert "ripples into **9 transitive packages**" in report_md

    # Fix Consolidation section
    assert "Fixing these 4 packages addresses 100% of all currently flagged risk across 5 alerts" in report_md
    assert "#1 Priority Fix: `ms`" in report_md


def test_export_report_debug_with_active_simulation():
    """Verify Markdown report generation for 'debug' with active compromise simulation."""
    data = load_cached_graph()
    G = build_dependency_graph(data)
    metrics = compute_structural_metrics(G)
    max_in = max(m["in_degree"] for m in metrics.values())
    max_trans = max(m["transitive_dependents_count"] for m in metrics.values())

    debug_metrics = metrics["debug"]
    debug_score = compute_composite_criticality("debug", debug_metrics, max_in, max_trans)
    explanation = generate_explanation("debug", debug_score, debug_metrics)
    sim = simulate_compromise(G, "debug")

    report_md = generate_scenario_report(
        package_name="debug",
        score_data=debug_score,
        metrics=debug_metrics,
        explanation=explanation,
        ecosystem="npm",
        active_source_label="Demo dataset (5 npm seeds)",
        snapshot_id=data.get("metadata", {}).get("snapshot_id"),
        simulation_result=sim,
        fix_report=None
    )

    # Simulation results
    assert "🚨 **Active Compromise Simulated**" in report_md
    assert "**Total Affected Packages:** **10** downstream components" in report_md
    assert "**Maximum Propagation Distance:** **2** hop(s)" in report_md
    assert "Threatened Application Seeds (3)" in report_md
    assert "`axios`" in report_md and "`express`" in report_md and "`morgan`" in report_md

    # Shortest attack paths
    assert "- **Target `express`:** `debug` ➔ `express`" in report_md
    assert "- **Target `morgan`:** `debug` ➔ `morgan`" in report_md
    assert "- **Target `axios`:** `debug` ➔ `https-proxy-agent` ➔ `axios`" in report_md


def test_export_report_dotenv_containment():
    """Verify zero-downstream containment status in report for root app 'dotenv'."""
    data = load_cached_graph()
    G = build_dependency_graph(data)
    metrics = compute_structural_metrics(G)
    max_in = max(m["in_degree"] for m in metrics.values())
    max_trans = max(m["transitive_dependents_count"] for m in metrics.values())

    dotenv_metrics = metrics["dotenv"]
    dotenv_score = compute_composite_criticality("dotenv", dotenv_metrics, max_in, max_trans)
    explanation = generate_explanation("dotenv", dotenv_score, dotenv_metrics)
    sim = simulate_compromise(G, "dotenv")

    report_md = generate_scenario_report(
        package_name="dotenv",
        score_data=dotenv_score,
        metrics=dotenv_metrics,
        explanation=explanation,
        ecosystem="npm",
        active_source_label="Demo dataset (5 npm seeds)",
        simulation_result=sim
    )

    assert "🛡️ **Zero-Downstream Root Application**" in report_md
    assert "completely contained" in report_md
    assert "| **Composite Criticality Score** | **5.2 / 100** |" in report_md
    assert "| **Assigned Risk Tier** | **LOW RISK** |" in report_md


def test_export_report_pypi_ecosystem():
    """Verify report generation for PyPI ecosystem package (typing-extensions)."""
    data = load_cached_pypi_graph()
    G = build_dependency_graph(data)
    metrics = compute_structural_metrics(G)
    max_in = max(m["in_degree"] for m in metrics.values())
    max_trans = max(m["transitive_dependents_count"] for m in metrics.values())

    te_metrics = metrics["typing-extensions"]
    te_score = compute_composite_criticality("typing-extensions", te_metrics, max_in, max_trans)
    explanation = generate_explanation("typing-extensions", te_score, te_metrics)
    sim = simulate_compromise(G, "typing-extensions")

    report_md = generate_scenario_report(
        package_name="typing-extensions",
        score_data=te_score,
        metrics=te_metrics,
        explanation=explanation,
        ecosystem="pypi",
        active_source_label="Demo dataset (5 PyPI seeds)",
        snapshot_id=data.get("metadata", {}).get("snapshot_id"),
        simulation_result=sim
    )

    assert "# 🛡️ RippleGuard Scenario Audit Report: `typing-extensions`" in report_md
    assert "- **Ecosystem:** `pypi`" in report_md
    assert "| **Composite Criticality Score** | **68.5 / 100** |" in report_md
    assert "| **Assigned Risk Tier** | **HIGH RISK** |" in report_md
    assert "Default Benign Baseline" in report_md
    assert "| **Confidence Assessment (FR-5.5)** | **Estimated (default baseline)** |" in report_md
    assert "**Total Affected Packages:** **9** downstream components" in report_md
