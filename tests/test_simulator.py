"""
test_simulator.py - Unit tests for FR-4.3: Multi-origin compromise propagation.

Tests:
1. Backward compatibility for single-node simulate_compromise()
2. Multi-origin compromise with overlapping blast radii (debug + mime-types)
3. Multi-origin compromise with non-overlapping blast radii
4. Edge cases: 0 origins, non-existent origins, mixed valid/invalid origins, 1-node list parity
"""

import os
import sys
import pytest
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetcher import load_cached_graph
from src.graph_builder import build_dependency_graph
from src.simulator import simulate_compromise, simulate_multi_compromise, simulate_monte_carlo


@pytest.fixture
def demo_graph():
    data = load_cached_graph()
    return build_dependency_graph(data)


def test_simulate_compromise_single_node_backward_compatibility(demo_graph):
    """Verify existing single-node simulate_compromise() call behaves identically."""
    sim = simulate_compromise(demo_graph, "debug")

    assert sim.compromised_node == "debug"
    assert sim.compromised_nodes == ["debug"]
    assert sim.affected_count == 10
    assert "debug" in sim.affected_nodes
    assert "express" in sim.affected_nodes
    assert "axios" in sim.affected_nodes
    assert sim.affected_seeds == ["axios", "express", "morgan"]
    assert sim.max_hops == 2
    assert sim.multi_origin_nodes == []
    assert sim.origin_reachability["express"] == {"debug": 1}
    assert sim.origin_reachability["axios"] == {"debug": 2}
    assert sim.hop_distances["express"] == 1
    assert sim.hop_distances["axios"] == 2
    assert sim.propagation_paths["axios"] == ["debug", "https-proxy-agent", "axios"]


def test_simulate_multi_compromise_overlapping_origins(demo_graph):
    """
    Verify multi-origin compromise with overlapping downstream blast radii.
    Origins: debug (10 nodes) and mime-types (9 nodes).
    Overlap (5 nodes): axios, body-parser, express, send, serve-static.
    Total union: 14 nodes.
    """
    sim = simulate_compromise(demo_graph, ["debug", "mime-types"])

    assert sim.compromised_nodes == ["debug", "mime-types"]
    assert sim.compromised_node == "debug, mime-types"
    assert sim.affected_count == 14

    # Verify multi-origin overlapping nodes
    expected_overlap = ["axios", "body-parser", "express", "send", "serve-static"]
    assert sim.multi_origin_nodes == expected_overlap

    # Verify shortest hop logic across origins
    # body-parser: debug is 1 hop, mime-types is 2 hops -> min hop must be 1 from debug
    assert sim.origin_reachability["body-parser"] == {"debug": 1, "mime-types": 2}
    assert sim.hop_distances["body-parser"] == 1
    assert sim.propagation_paths["body-parser"] == ["debug", "body-parser"]

    # axios: debug is 2 hops, mime-types is 2 hops -> min hop is 2
    assert sim.origin_reachability["axios"] == {"debug": 2, "mime-types": 2}
    assert sim.hop_distances["axios"] == 2

    # express: debug is 1 hop, mime-types is 1 hop -> min hop is 1
    assert sim.origin_reachability["express"] == {"debug": 1, "mime-types": 1}
    assert sim.hop_distances["express"] == 1

    # Non-overlapping nodes only reached from one origin
    assert sim.origin_reachability["morgan"] == {"debug": 1}
    assert sim.origin_reachability["accepts"] == {"mime-types": 1}
    assert sim.origin_reachability["type-is"] == {"mime-types": 1}
    assert sim.origin_reachability["form-data"] == {"mime-types": 1}

    # Union of application seeds
    assert sim.affected_seeds == ["axios", "express", "morgan"]

    # Level grouping
    assert sim.levels[0] == ["debug", "mime-types"]
    assert "axios" in sim.levels[2]
    assert "serve-static" in sim.levels[2]
    assert "express" in sim.levels[1]


def test_simulate_multi_compromise_non_overlapping_origins():
    """Verify multi-origin compromise with two completely independent disjoint trees."""
    G = nx.DiGraph()
    # Tree 1: seed1 -> dep1 -> origin1
    G.add_edge("seed1", "dep1")
    G.add_edge("dep1", "origin1")
    G.nodes["seed1"]["is_seed"] = True
    G.nodes["dep1"]["is_seed"] = False
    G.nodes["origin1"]["is_seed"] = False

    # Tree 2: seed2 -> dep2 -> origin2
    G.add_edge("seed2", "dep2")
    G.add_edge("dep2", "origin2")
    G.nodes["seed2"]["is_seed"] = True
    G.nodes["dep2"]["is_seed"] = False
    G.nodes["origin2"]["is_seed"] = False

    sim = simulate_multi_compromise(G, ["origin1", "origin2"])

    assert sim.affected_count == 6
    assert set(sim.affected_nodes) == {"origin1", "dep1", "seed1", "origin2", "dep2", "seed2"}
    assert sim.multi_origin_nodes == []  # Zero overlap
    assert sim.affected_seeds == ["seed1", "seed2"]

    # Each node has exactly one origin recorded
    assert sim.origin_reachability["seed1"] == {"origin1": 2}
    assert sim.origin_reachability["seed2"] == {"origin2": 2}
    assert sim.hop_distances["seed1"] == 2
    assert sim.hop_distances["seed2"] == 2


def test_simulate_multi_compromise_edge_cases(demo_graph):
    """Verify origin-count edge cases: 0 origins, non-existent, and 1-origin list."""
    # 1. Zero origins
    sim_empty = simulate_compromise(demo_graph, [])
    assert sim_empty.affected_count == 0
    assert sim_empty.affected_nodes == []
    assert sim_empty.affected_seeds == []
    assert sim_empty.multi_origin_nodes == []
    assert sim_empty.hop_distances == {}

    # 2. Non-existent origin
    sim_none = simulate_compromise(demo_graph, ["non-existent-pkg-abc"])
    assert sim_none.affected_count == 0
    assert sim_none.affected_nodes == []

    # 3. Mixed valid and non-existent origins (should filter out invalid)
    sim_mixed = simulate_compromise(demo_graph, ["debug", "non-existent-pkg-abc"])
    assert sim_mixed.compromised_nodes == ["debug"]
    assert sim_mixed.affected_count == 10

    # 4. 1-node list matches single-node call exactly
    sim_single_str = simulate_compromise(demo_graph, "debug")
    sim_single_list = simulate_compromise(demo_graph, ["debug"])
    assert sim_single_str.affected_count == sim_single_list.affected_count
    assert sim_single_str.affected_nodes == sim_single_list.affected_nodes
    assert sim_single_str.affected_seeds == sim_single_list.affected_seeds
    assert sim_single_str.hop_distances == sim_single_list.hop_distances
    assert sim_single_str.propagation_paths == sim_single_list.propagation_paths
    assert sim_single_str.levels == sim_single_list.levels


# ---------------------------------------------------------------------------
# FR-4.4: Monte Carlo Probabilistic Propagation Tests
# ---------------------------------------------------------------------------

def test_monte_carlo_fully_pinned_near_zero_infection():
    """
    A graph with very low probability edges (e.g. pinned exact versions)
    should show near-zero infection probability on non-origin nodes.
    """
    G = nx.DiGraph()
    # Chain: seed -> mid -> origin (seed depends on mid, mid depends on origin)
    G.add_node("origin", is_seed=False)
    G.add_node("mid", is_seed=False)
    G.add_node("seed", is_seed=True)
    G.add_edge("mid", "origin", probability=0.01, version_spec="1.0.0")
    G.add_edge("seed", "mid", probability=0.01, version_spec="1.0.0")

    result = simulate_monte_carlo(G, "origin", n_trials=1000, seed=42)

    assert result.infection_probability["origin"] == 1.0
    # Downstream nodes have near-zero propagation
    assert result.infection_probability.get("mid", 0.0) <= 0.05
    assert result.infection_probability.get("seed", 0.0) <= 0.01
    assert "mid" in result.partial_propagation_nodes
    assert "seed" in result.partial_propagation_nodes


def test_monte_carlo_fully_unpinned_converges_to_bfs():
    """
    When all edges have propagation probability 1.0, Monte Carlo converges
    exactly to the deterministic BFS result.
    """
    G = nx.DiGraph()
    # Tree: seed -> a -> origin, seed -> b -> origin
    for n in ["origin", "a", "b", "seed"]:
        G.add_node(n, is_seed=(n == "seed"))
    G.add_edge("a", "origin", probability=1.0)
    G.add_edge("b", "origin", probability=1.0)
    G.add_edge("seed", "a", probability=1.0)
    G.add_edge("seed", "b", probability=1.0)

    result = simulate_monte_carlo(G, "origin", n_trials=500, seed=42)
    bfs_result = simulate_multi_compromise(G, ["origin"])

    # All BFS-affected nodes should have 100% infection probability
    assert set(result.infection_probability.keys()) == set(bfs_result.affected_nodes)
    for node in bfs_result.affected_nodes:
        assert result.infection_probability[node] == 1.0
        assert result.infection_std[node] == 0.0

    # No partial propagation nodes when all edges propagate with certainty
    assert result.partial_propagation_nodes == []
    assert result.confidence == 1.0
    assert result.deterministic_result.confidence == 1.0


def test_monte_carlo_reproducibility_with_fixed_seed(demo_graph):
    """
    Simulations with the same random seed must produce byte-for-byte identical results.
    """
    r1 = simulate_monte_carlo(demo_graph, ["debug", "mime-types"], n_trials=500, seed=12345)
    r2 = simulate_monte_carlo(demo_graph, ["debug", "mime-types"], n_trials=500, seed=12345)

    assert r1.infection_probability == r2.infection_probability
    assert r1.infection_count == r2.infection_count
    assert r1.infection_std == r2.infection_std
    assert r1.confidence == r2.confidence
    assert r1.partial_propagation_nodes == r2.partial_propagation_nodes


def test_monte_carlo_mixed_probability_variance(demo_graph):
    """
    On the real npm demo graph with mixed version pin constraints, verify
    genuine variance, non-zero std-devs, and identification of partial-propagation nodes.
    """
    result = simulate_monte_carlo(demo_graph, ["debug", "mime-types"], n_trials=1000, seed=42)

    # Origins are always 100%
    assert result.infection_probability["debug"] == 1.0
    assert result.infection_probability["mime-types"] == 1.0

    # Downstream packages show genuine variance
    assert 0.0 < result.confidence < 1.0
    assert result.deterministic_result is not None
    assert result.deterministic_result.confidence == result.confidence

    # Packages with probabilistic propagation (p < 1.0) have std_dev > 0
    intermediate_nodes = [n for n in result.infection_probability if n not in ["debug", "mime-types"]]
    assert len(intermediate_nodes) > 0
    variable_nodes = [n for n in intermediate_nodes if result.infection_probability[n] < 1.0]
    assert len(variable_nodes) > 0
    for node in variable_nodes:
        assert result.infection_std[node] > 0.0

    # Core value-add: verify partial propagation nodes where BFS says affected but MC < 95%
    assert len(result.partial_propagation_nodes) > 0
    for node in result.partial_propagation_nodes:
        assert node in result.deterministic_result.affected_nodes
        assert result.infection_probability[node] < 0.95
        assert result.infection_std[node] > 0.0


def test_monte_carlo_edge_cases(demo_graph):
    """Test empty origin set and non-existent origins."""
    r_empty = simulate_monte_carlo(demo_graph, [], n_trials=100)
    assert r_empty.infection_probability == {}
    assert r_empty.confidence == 0.0
    assert r_empty.deterministic_result is None

    r_invalid = simulate_monte_carlo(demo_graph, ["non-existent-pkg-xyz"], n_trials=100)
    assert r_invalid.infection_probability == {}
    assert r_invalid.confidence == 0.0
