"""
Unit tests for Fix Consolidation ("Fix This First") engine in src/fix_consolidator.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetcher import load_cached_graph
from src.graph_builder import build_dependency_graph, compute_structural_metrics
from src.scoring import compute_composite_criticality
from src.fix_consolidator import consolidate_fixes, FixConsolidationReport, ConsolidatedFix
from src.models import WeightingConfig


def test_fix_consolidation_engine():
    raw = load_cached_graph()
    G = build_dependency_graph(raw)
    metrics = compute_structural_metrics(G)
    max_in = max(m["in_degree"] for m in metrics.values())
    max_tr = max(m["transitive_dependents_count"] for m in metrics.values())
    scores = {n: compute_composite_criticality(n, metrics[n], max_in, max_tr) for n in G.nodes()}

    # Run consolidation under default weights
    report = consolidate_fixes(G, scores, metrics)

    assert isinstance(report, FixConsolidationReport)
    assert report.total_flagged_packages == 5
    assert report.total_flagged_blast_radius == 18
    assert len(report.recommended_fixes) >= 2
    assert report.top_n_coverage_pct == 100.0

    # Verify rank 1 fix covers the most
    rank1 = report.recommended_fixes[0]
    assert rank1.rank == 1
    assert rank1.package == "ms"
    assert "debug" in rank1.subsumed_flagged_packages
    assert rank1.cumulative_coverage_pct == 61.1
    assert rank1.effort_tier == "Low"
    assert rank1.cost_impact_ratio > 0.0

    # Verify rank 2 fix adds substantial coverage
    rank2 = report.recommended_fixes[1]
    assert rank2.rank == 2
    assert rank2.package == "mime-types"
    assert rank2.cumulative_coverage_pct == 83.3
    assert rank2.effort_tier == "Low"

    # Verify empty flagged scenario
    empty_report = consolidate_fixes(G, scores, metrics, target_tiers=["NON_EXISTENT"])
    assert empty_report.total_flagged_packages == 0
    assert len(empty_report.recommended_fixes) == 0

    print(f"Fix Consolidation Test Passed: {report.headline_stat}")


def test_cost_impact_vs_coverage_ranking_reorder():
    """
    FR-5.2: Verify that cost/impact composite reorders priorities compared to raw coverage-%.
    In the demo graph:
      - 'depd' has higher marginal coverage (2 packages = 11.1%) but High effort (cost 3.0) -> ROI 3.70
      - 'on-finished' has lower marginal coverage (1 package = 5.6%) but Low effort (cost 1.0) -> ROI 5.56
    Under cost/impact ROI, on-finished outranks depd (Rank 3 vs Rank 4).
    Under coverage_only, depd outranks on-finished.
    """
    raw = load_cached_graph()
    G = build_dependency_graph(raw)
    metrics = compute_structural_metrics(G)
    max_in = max(m["in_degree"] for m in metrics.values())
    max_tr = max(m["transitive_dependents_count"] for m in metrics.values())
    scores = {n: compute_composite_criticality(n, metrics[n], max_in, max_tr) for n in G.nodes()}

    # 1. Cost/Impact ROI ranking (FR-5.2 primary)
    roi_report = consolidate_fixes(G, scores, metrics, ranking_strategy="cost_impact")
    roi_packages = [f.package for f in roi_report.recommended_fixes]

    # 2. Coverage-only ranking (FR-5.2 baseline comparison)
    cov_report = consolidate_fixes(G, scores, metrics, ranking_strategy="coverage_only")
    cov_packages = [f.package for f in cov_report.recommended_fixes]

    # Baseline coverage order: ms (11) -> mime-types (4) -> depd (2) -> on-finished (1)
    assert cov_packages == ["ms", "mime-types", "depd", "on-finished"]
    assert cov_report.recommended_fixes[2].package == "depd"
    assert cov_report.recommended_fixes[3].package == "on-finished"

    # Cost/Impact ROI order: ms (ROI 61.1) -> mime-types (ROI 22.2) -> on-finished (ROI 5.56) -> depd (ROI 3.70)
    assert roi_packages == ["ms", "mime-types", "on-finished", "depd"]
    assert roi_report.recommended_fixes[2].package == "on-finished"
    assert roi_report.recommended_fixes[2].effort_tier == "Low"
    assert roi_report.recommended_fixes[2].cost_impact_ratio == 5.56

    assert roi_report.recommended_fixes[3].package == "depd"
    assert roi_report.recommended_fixes[3].effort_tier == "High"
    assert roi_report.recommended_fixes[3].cost_impact_ratio == 3.70


def test_synthetic_low_coverage_low_effort_outranks_high_coverage_high_effort():
    """
    FR-5.2 Requirement 6:
    Explicit unit test showing lower-coverage/lower-effort fix outranks a
    higher-coverage/higher-effort fix under the new composite.
    """
    import networkx as nx
    from src.models import CriticalityScore
    from src.fix_consolidator import consolidate_fixes

    # Build a simple synthetic graph:
    # Package A -> 6 downstream packages (60% coverage), High effort (cost 3.0) -> ROI = 20.0
    # Package B -> 4 downstream packages (40% coverage), Low effort (cost 1.0) -> ROI = 40.0
    G = nx.DiGraph()
    # Downstream dependents of A
    for i in range(1, 7):
        G.add_edge(f"dep_a_{i}", "pkg_a")
    # Downstream dependents of B (disjoint)
    for i in range(1, 5):
        G.add_edge(f"dep_b_{i}", "pkg_b")

    from src.models import WeightingConfig

    cfg = WeightingConfig()
    scores = {
        "pkg_a": CriticalityScore(
            node_id="pkg_a", composite_score=80.0, structural_subscore=50.0,
            vulnerability_subscore=30.0, weighting_config=cfg, tier="CRITICAL",
            tier_color="#e63946", cvss=7.0
        ),
        "pkg_b": CriticalityScore(
            node_id="pkg_b", composite_score=75.0, structural_subscore=45.0,
            vulnerability_subscore=30.0, weighting_config=cfg, tier="CRITICAL",
            tier_color="#e63946", cvss=6.5
        ),
    }
    for i in range(1, 7):
        scores[f"dep_a_{i}"] = CriticalityScore(
            node_id=f"dep_a_{i}", composite_score=10.0, structural_subscore=5.0,
            vulnerability_subscore=5.0, weighting_config=cfg, tier="LOW",
            tier_color="#2a9d8f", cvss=1.0
        )
    for i in range(1, 5):
        scores[f"dep_b_{i}"] = CriticalityScore(
            node_id=f"dep_b_{i}", composite_score=10.0, structural_subscore=5.0,
            vulnerability_subscore=5.0, weighting_config=cfg, tier="LOW",
            tier_color="#2a9d8f", cvss=1.0
        )

    metrics = {n: {"in_degree": 0, "transitive_dependents_count": 0, "affected_seeds": []} for n in G.nodes()}

    custom_actions = {
        "pkg_a": "Replace dependency entirely",  # High effort (cost 3.0)
        "pkg_b": "Pin/upgrade version",          # Low effort (cost 1.0)
    }

    # Under cost/impact composite: pkg_b (ROI 40.0) outranks pkg_a (ROI 20.0)
    roi_report = consolidate_fixes(
        G, scores, metrics,
        target_tiers=["CRITICAL"],
        package_actions=custom_actions,
        ranking_strategy="cost_impact"
    )
    assert len(roi_report.recommended_fixes) == 2
    assert roi_report.recommended_fixes[0].package == "pkg_b"
    assert roi_report.recommended_fixes[0].effort_tier == "Low"
    assert roi_report.recommended_fixes[1].package == "pkg_a"
    assert roi_report.recommended_fixes[1].effort_tier == "High"

    # Under coverage_only: pkg_a (6 newly covered) outranks pkg_b (4 newly covered)
    cov_report = consolidate_fixes(
        G, scores, metrics,
        target_tiers=["CRITICAL"],
        package_actions=custom_actions,
        ranking_strategy="coverage_only"
    )
    assert len(cov_report.recommended_fixes) == 2
    assert cov_report.recommended_fixes[0].package == "pkg_a"
    assert cov_report.recommended_fixes[1].package == "pkg_b"


def test_mitigation_effort_fallback_to_medium():
    """
    FR-5.2 Requirement 5:
    Preserve backward compatibility: if effort data is unavailable for a given
    mitigation type, default to Medium and don't crash.
    """
    from src.fix_consolidator import get_mitigation_effort, get_effort_cost

    assert get_mitigation_effort(None) == "Medium"
    assert get_mitigation_effort("") == "Medium"
    assert get_mitigation_effort("CompletelyUnknownActionType") == "Medium"
    assert get_effort_cost("Medium") == 2.0
    assert get_effort_cost("UNKNOWN") == 2.0


def test_fr52_effort_assignment_taxonomy_and_costs():
    """
    FR-5.2 Requirement 1: Verify effort tier assignment for all canonical action types.
    """
    from src.fix_consolidator import get_mitigation_effort, get_effort_cost

    # Canonical taxonomy specified in FR-5.2
    assert get_mitigation_effort("Pin to exact version / lockfile digest") == "Low"
    assert get_effort_cost("Low") == 1.0

    assert get_mitigation_effort("Upgrade to patched minor version") == "Low-Medium"
    assert get_effort_cost("Low-Medium") == 1.5

    assert get_mitigation_effort("Upgrade across major version (breaking changes)") == "High"
    assert get_effort_cost("High") == 3.0

    assert get_mitigation_effort("Replace dependency entirely") == "High"
    assert get_effort_cost("High") == 3.0

    assert get_mitigation_effort("Fork and audit") == "Very High"
    assert get_effort_cost("Very High") == 4.0

    assert get_mitigation_effort("Add monitoring / CI gate") == "Low"
    assert get_effort_cost("Low") == 1.0


def test_fr52_derive_package_action():
    """
    FR-5.2 Requirement 1: Derive action type from edge pin status and package metadata.
    """
    import networkx as nx
    from src.fix_consolidator import derive_package_action

    G = nx.DiGraph()
    G.add_node("child_loose")
    G.add_node("parent_loose")
    # parent depends on child with floating caret -> should pin
    G.add_edge("parent_loose", "child_loose", version_spec="^1.2.0")

    G.add_node("child_pinned")
    G.add_node("parent_pinned")
    # parent depends on child with exact pin -> should upgrade minor
    G.add_edge("parent_pinned", "child_pinned", version_spec="1.2.0")

    action_loose = derive_package_action("child_loose", G=G)
    assert action_loose == "Pin to exact version / lockfile digest"

    action_pinned = derive_package_action("child_pinned", G=G)
    assert action_pinned == "Upgrade to patched minor version"

    # Fallback when no edge info is present
    action_fallback = derive_package_action("random_unknown_pkg")
    assert action_fallback == "Upgrade to patched minor version"


def test_fr52_dual_ranking_and_exact_coverage_percentages():
    """
    FR-5.2 Requirements 2 & 5:
    - Pure coverage ranking produces: ms -> mime-types -> depd -> on-finished
    - Efficiency (cost/impact) ranking produces: ms -> mime-types -> on-finished -> depd
    - Both lists are simultaneously surfaced on FixConsolidationReport
    - Coverage percentages for coverage-only are byte-for-byte unchanged:
      ms: 61.1%, mime-types: 83.3%, depd: 94.4%, on-finished: 100.0%
    """
    raw = load_cached_graph()
    G = build_dependency_graph(raw)
    metrics = compute_structural_metrics(G)
    max_in = max(m["in_degree"] for m in metrics.values())
    max_tr = max(m["transitive_dependents_count"] for m in metrics.values())
    scores = {n: compute_composite_criticality(n, metrics[n], max_in, max_tr) for n in G.nodes()}

    report = consolidate_fixes(G, scores, metrics, ranking_strategy="cost_impact")

    # Both lists present on the same report
    assert len(report.coverage_ranked_fixes) == 4
    assert len(report.efficiency_ranked_fixes) == 4

    cov_pkgs = [f.package for f in report.coverage_ranked_fixes]
    eff_pkgs = [f.package for f in report.efficiency_ranked_fixes]

    # Verify genuinely different order
    assert cov_pkgs == ["ms", "mime-types", "depd", "on-finished"]
    assert eff_pkgs == ["ms", "mime-types", "on-finished", "depd"]

    # Verify exact coverage percentages are unchanged
    assert report.coverage_ranked_fixes[0].cumulative_coverage_pct == 61.1
    assert report.coverage_ranked_fixes[1].cumulative_coverage_pct == 83.3
    assert report.coverage_ranked_fixes[2].cumulative_coverage_pct == 94.4
    assert report.coverage_ranked_fixes[3].cumulative_coverage_pct == 100.0


if __name__ == "__main__":
    test_fix_consolidation_engine()
    test_cost_impact_vs_coverage_ranking_reorder()
    test_synthetic_low_coverage_low_effort_outranks_high_coverage_high_effort()
    test_mitigation_effort_fallback_to_medium()
    test_fr52_effort_assignment_taxonomy_and_costs()
    test_fr52_derive_package_action()
    test_fr52_dual_ranking_and_exact_coverage_percentages()
    print("All Fix Consolidator tests passed!")

