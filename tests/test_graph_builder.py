"""
tests/test_graph_builder.py - Comprehensive test suite for FR-3.1 Betweenness Centrality.

Covers:
1. Betweenness values match nx.betweenness_centrality() baseline exactly on npm graph.
2. Betweenness values match nx.betweenness_centrality() baseline exactly on PyPI graph.
3. Default weighting config (weight_betweenness=0.0) leaves demo scores byte-for-byte unchanged:
   debug=79.5, ms=60.1, mime-types=58.6, depd=45.8, on-finished=45.4, dotenv=5.2.
4. Size-gating threshold behavior: skips large graphs gracefully, sets betweenness_skipped=True,
   and completes instantly without hanging.
5. Structural bottleneck discovery: http-errors and send act as bridges with higher betweenness
   than leaf nodes like ms (betweenness=0.0) despite ms having maximum transitive reachability (10).
6. WeightingConfig 4-weight normalization and 3-argument backwards compatibility.
"""

import sys
import os
import pytest
import networkx as nx

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetcher import load_cached_graph, load_cached_pypi_graph
from src.graph_builder import (
    build_dependency_graph,
    compute_structural_metrics,
    BETWEENNESS_MAX_NODES
)
from src.models import WeightingConfig
from src.scoring import compute_composite_criticality


def test_betweenness_matches_networkx_baseline_npm():
    """1. Verify betweenness values match nx.betweenness_centrality() baseline exactly on npm graph."""
    raw = load_cached_graph()
    G = build_dependency_graph(raw)
    metrics = compute_structural_metrics(G)

    expected_bc = nx.betweenness_centrality(G)
    assert len(metrics) == len(expected_bc) == 64

    for node, expected_val in expected_bc.items():
        actual_val = metrics[node]["betweenness_centrality"]
        assert actual_val == pytest.approx(expected_val, abs=1e-9), (
            f"Mismatch for node {node}: expected {expected_val}, got {actual_val}"
        )
        assert metrics[node]["betweenness_skipped"] is False


def test_betweenness_matches_networkx_baseline_pypi():
    """2. Verify betweenness values match nx.betweenness_centrality() baseline exactly on PyPI graph."""
    raw = load_cached_pypi_graph()
    G = build_dependency_graph(raw)
    metrics = compute_structural_metrics(G)

    expected_bc = nx.betweenness_centrality(G)
    assert len(metrics) == len(expected_bc) == 35

    for node, expected_val in expected_bc.items():
        actual_val = metrics[node]["betweenness_centrality"]
        assert actual_val == pytest.approx(expected_val, abs=1e-9), (
            f"Mismatch for node {node}: expected {expected_val}, got {actual_val}"
        )
        assert metrics[node]["betweenness_skipped"] is False


def test_default_weight_preserves_existing_scores():
    """3. Verify default weighting (weight_betweenness=0.0) leaves demo scores byte-for-byte unchanged."""
    raw = load_cached_graph()
    G = build_dependency_graph(raw)
    metrics = compute_structural_metrics(G)

    max_in = max(m["in_degree"] for m in metrics.values())
    max_tr = max(m["transitive_dependents_count"] for m in metrics.values())
    max_bw = max((m.get("betweenness_centrality", 0.0) for m in metrics.values()), default=0.0)

    cfg = WeightingConfig()
    assert cfg.weight_betweenness == 0.0

    scores = {
        n: compute_composite_criticality(
            n, metrics[n], max_in, max_tr, weight_config=cfg, max_betweenness=max_bw
        )
        for n in G.nodes()
    }

    # Critical invariants from FRD
    assert scores["debug"].score == 79.5
    assert scores["ms"].score == 60.1
    assert scores["mime-types"].score == 58.6
    assert scores["depd"].score == 45.8
    assert scores["on-finished"].score == 45.4
    assert scores["dotenv"].score == 5.2

    # All nodes must have scores bounded between 0 and 100
    for n, sc in scores.items():
        assert 0.0 <= sc.score <= 100.0


def test_size_gating_threshold_skips_large_graphs():
    """4. Verify size-gating threshold behavior: skips large graphs gracefully without hanging."""
    raw = load_cached_graph()
    G = build_dependency_graph(raw)

    # With default threshold (500), 64-node graph is computed live
    assert G.number_of_nodes() <= BETWEENNESS_MAX_NODES
    normal_metrics = compute_structural_metrics(G)
    assert normal_metrics["debug"]["betweenness_skipped"] is False
    assert normal_metrics["debug"]["betweenness_centrality"] > 0.0

    # Pass lower threshold (e.g. 50 nodes), graph (64 nodes) must be skipped gracefully
    gated_metrics = compute_structural_metrics(G, betweenness_threshold=50)
    for node, m in gated_metrics.items():
        assert m["betweenness_skipped"] is True
        assert m["betweenness_centrality"] == 0.0
        # In-degree, out-degree, transitive reachability are still correctly computed
        assert m["in_degree"] == normal_metrics[node]["in_degree"]
        assert m["transitive_dependents_count"] == normal_metrics[node]["transitive_dependents_count"]

    # Also test with a synthetic graph of 501 nodes to ensure threshold triggers at > BETWEENNESS_MAX_NODES
    G_large = nx.DiGraph()
    for i in range(501):
        G_large.add_node(f"pkg_{i}")
        if i > 0:
            G_large.add_edge(f"pkg_{i-1}", f"pkg_{i}")

    large_metrics = compute_structural_metrics(G_large)
    assert len(large_metrics) == 501
    assert large_metrics["pkg_0"]["betweenness_skipped"] is True
    assert large_metrics["pkg_0"]["betweenness_centrality"] == 0.0


def test_betweenness_reveals_structural_bottlenecks():
    """5. Verify betweenness identifies structural bridges that in-degree or reachability alone miss."""
    raw = load_cached_graph()
    G = build_dependency_graph(raw)
    metrics = compute_structural_metrics(G)

    max_in = max(m["in_degree"] for m in metrics.values())
    max_tr = max(m["transitive_dependents_count"] for m in metrics.values())
    max_bw = max((m.get("betweenness_centrality", 0.0) for m in metrics.values()), default=0.0)

    # In-degree / reachability comparison:
    # 'debug' has high in-degree (7) and high transitive (9)
    # 'ms' has maximum transitive dependents (10)
    # 'http-errors' has lower in-degree (3) and lower transitive (4)
    assert metrics["debug"]["in_degree"] > metrics["http-errors"]["in_degree"]
    assert metrics["ms"]["transitive_dependents_count"] > metrics["http-errors"]["transitive_dependents_count"]

    # BUT http-errors has significantly higher betweenness centrality than both!
    assert metrics["http-errors"]["betweenness_centrality"] > metrics["debug"]["betweenness_centrality"]
    assert metrics["ms"]["betweenness_centrality"] == 0.0  # ms is a terminal leaf (out-degree=0)
    assert metrics["http-errors"]["betweenness_centrality"] == max_bw  # #1 in the graph (0.004096)

    # When betweenness weight is enabled, http-errors criticality increases to reflect bridge risk
    cfg_default = WeightingConfig(0.35, 0.40, 0.25, 0.0)
    cfg_with_bw = WeightingConfig(0.25, 0.25, 0.25, 0.25)

    score_def = compute_composite_criticality(
        "http-errors", metrics["http-errors"], max_in, max_tr, weight_config=cfg_default, max_betweenness=max_bw
    )
    score_bw = compute_composite_criticality(
        "http-errors", metrics["http-errors"], max_in, max_tr, weight_config=cfg_with_bw, max_betweenness=max_bw
    )

    # Structural subscore and overall composite score increase significantly
    assert score_bw.structural_subscore > score_def.structural_subscore
    assert score_bw.score > score_def.score


def test_weighting_config_normalization_and_backwards_compatibility():
    """6. Verify WeightingConfig 4-weight normalization and 3-argument backwards compatibility."""
    # 1. Default constructor
    cfg = WeightingConfig()
    assert cfg.weight_cvss == 0.35
    assert cfg.weight_transitive == 0.40
    assert cfg.weight_indegree == 0.25
    assert cfg.weight_betweenness == 0.0

    norm_cfg = cfg.normalize()
    assert norm_cfg.weight_cvss == pytest.approx(0.35)
    assert norm_cfg.weight_transitive == pytest.approx(0.40)
    assert norm_cfg.weight_indegree == pytest.approx(0.25)
    assert norm_cfg.weight_betweenness == pytest.approx(0.0)
    assert (
        norm_cfg.weight_cvss
        + norm_cfg.weight_transitive
        + norm_cfg.weight_indegree
        + norm_cfg.weight_betweenness
    ) == pytest.approx(1.0)

    # 2. 3-argument constructor (legacy callers)
    cfg3 = WeightingConfig(0.50, 0.30, 0.20)
    assert cfg3.weight_cvss == 0.50
    assert cfg3.weight_transitive == 0.30
    assert cfg3.weight_indegree == 0.20
    assert cfg3.weight_betweenness == 0.0
    norm3 = cfg3.normalize()
    assert (
        norm3.weight_cvss
        + norm3.weight_transitive
        + norm3.weight_indegree
        + norm3.weight_betweenness
    ) == pytest.approx(1.0)

    # 3. 4-argument constructor with non-zero betweenness
    cfg4 = WeightingConfig(25, 25, 25, 25)
    norm4 = cfg4.normalize()
    assert norm4.weight_cvss == pytest.approx(0.25)
    assert norm4.weight_transitive == pytest.approx(0.25)
    assert norm4.weight_indegree == pytest.approx(0.25)
    assert norm4.weight_betweenness == pytest.approx(0.25)

    # 4. Zero total fallback
    zero_cfg = WeightingConfig(0, 0, 0, 0).normalize()
    assert zero_cfg.weight_cvss == 0.35
    assert zero_cfg.weight_transitive == 0.40
    assert zero_cfg.weight_indegree == 0.25
    assert zero_cfg.weight_betweenness == 0.0
