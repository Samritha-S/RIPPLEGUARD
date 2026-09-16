"""
test_pypi_fetcher.py - Tests for Phase B2 (FR-1.2: Multi-Ecosystem Support - PyPI)
Verifies PEP 508 requirement parsing, PyPI metadata ingestion, offline cache loading,
and full downstream analytical pipeline execution (graph construction, structural metrics,
composite criticality scoring, BFS compromise simulation, and Fix Consolidation).
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetcher import (
    parse_pypi_requirement,
    fetch_pypi_package_metadata,
    load_cached_pypi_graph,
    DEFAULT_PYPI_CACHE_PATH
)
from src.graph_builder import build_dependency_graph, compute_structural_metrics
from src.scoring import compute_composite_criticality
from src.simulator import simulate_compromise
from src.fix_consolidator import consolidate_fixes


def test_parse_pypi_requirement():
    """Verify PEP 508 requirement parsing and extra filtering."""
    # Standard requirement
    res = parse_pypi_requirement("requests<3,>=2.0")
    assert res == ("requests", "<3,>=2.0")

    # Requirement with extra filter -> should be ignored (None)
    assert parse_pypi_requirement('PySocks!=1.5.7; extra == "socks"') is None
    assert parse_pypi_requirement("flake8-docstrings; extra == 'lint'") is None

    # Requirement with python_version marker -> should keep dependency
    res_pyver = parse_pypi_requirement('importlib-metadata>=0.12; python_version<"3.8"')
    assert res_pyver == ("importlib-metadata", ">=0.12")

    # Requirement with package extras bracket -> bracket stripped from name
    res_bracket = parse_pypi_requirement("uvicorn[standard]>=0.12.0")
    assert res_bracket == ("uvicorn", ">=0.12.0")

    # Underscore normalization to hyphen
    res_underscore = parse_pypi_requirement("typing_extensions>=4.0")
    assert res_underscore == ("typing-extensions", ">=4.0")

    # Empty / comment
    assert parse_pypi_requirement("") is None
    assert parse_pypi_requirement("# comment") is None


def test_fetch_pypi_package_metadata_mocked():
    """Verify fetch_pypi_package_metadata parses JSON response correctly."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "info": {
            "version": "1.2.3",
            "summary": "A mock Python package",
            "license_expression": "Apache-2.0",
            "author": "Alice Developer",
            "author_email": "alice@example.com",
            "maintainer": None,
            "maintainer_email": "Bob Maintainer <bob@example.com>",
            "requires_dist": [
                "click>=8.0",
                "colorama; extra == 'colors'",
                "typing-extensions>=4.1"
            ]
        },
        "releases": {
            "1.2.3": [
                {"upload_time_iso_8601": "2026-01-15T12:00:00Z"}
            ]
        }
    }
    mock_session.get.return_value = mock_response

    meta = fetch_pypi_package_metadata("mock_pkg", session=mock_session)
    assert meta is not None
    assert meta["id"] == "mock-pkg"
    assert meta["name"] == "mock-pkg"
    assert meta["ecosystem"] == "pypi"
    assert meta["version"] == "1.2.3"
    assert meta["license"] == "Apache-2.0"
    assert meta["publish_date"] == "2026-01-15T12:00:00Z"
    assert meta["downloads"] is None
    assert "Alice Developer" in meta["maintainers"]
    assert "Bob Maintainer" in meta["maintainers"]
    assert "click" in meta["direct_deps"]
    assert "typing-extensions" in meta["direct_deps"]
    assert "colorama" not in meta["direct_deps"]


def test_load_cached_pypi_graph_offline():
    """Verify PyPI offline cached graph file structure, snapshot metadata, and node tagging."""
    assert os.path.exists(DEFAULT_PYPI_CACHE_PATH), "PyPI cache file must exist"
    data = load_cached_pypi_graph(DEFAULT_PYPI_CACHE_PATH)

    meta = data.get("metadata", {})
    assert "snapshot_id" in meta
    assert meta.get("ecosystem") == "pypi"
    assert meta.get("node_count") == 35
    assert meta.get("edge_count") == 38
    assert meta.get("seeds") == ["requests", "flask", "django", "fastapi", "pytest"]

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    assert len(nodes) == 35
    assert len(edges) == 38

    # Ensure every single node is tagged with ecosystem="pypi"
    for n in nodes:
        assert n.get("ecosystem") == "pypi", f"Node {n.get('id')} must have ecosystem='pypi'"

    # Verify real metadata on key seeds
    node_map = {n["id"]: n for n in nodes}
    assert "requests" in node_map
    req = node_map["requests"]
    assert req["license"] == "Apache-2.0"
    assert req["publish_date"] is not None
    assert req["downloads"] is None
    assert isinstance(req["maintainers"], list) and len(req["maintainers"]) >= 1


def test_pypi_graph_downstream_pipeline():
    """Verify scoring, BFS compromise propagation, and Fix Consolidation on PyPI graph."""
    data = load_cached_pypi_graph()
    G = build_dependency_graph(data)
    assert len(G.nodes()) == 35
    assert len(G.edges()) == 38

    metrics = compute_structural_metrics(G)
    max_in = max(m["in_degree"] for m in metrics.values())
    max_trans = max(m["transitive_dependents_count"] for m in metrics.values())

    # typing-extensions should be the top structural dependency in the PyPI seed ecosystem
    assert "typing-extensions" in metrics
    te_metrics = metrics["typing-extensions"]
    assert te_metrics["in_degree"] == 6
    assert te_metrics["transitive_dependents_count"] == 8

    # Scoring
    scores = {}
    for nid in G.nodes():
        scores[nid] = compute_composite_criticality(
            package_name=nid,
            metrics=metrics[nid],
            max_in_degree=max_in,
            max_transitive=max_trans
        )

    assert scores["typing-extensions"].tier == "HIGH"
    assert scores["typing-extensions"].composite_score >= 65.0

    # BFS Compromise Simulation
    sim = simulate_compromise(G, "typing-extensions")
    assert sim.compromised_node == "typing-extensions"
    assert sim.affected_count == 9
    assert "fastapi" in sim.affected_nodes
    assert "django" in sim.affected_nodes
    assert "pytest" in sim.affected_nodes

    # Fix Consolidation
    fixes = consolidate_fixes(G, scores, metrics, target_tiers=["CRITICAL", "HIGH", "MEDIUM"])
    assert fixes.total_flagged_packages >= 1
    assert len(fixes.recommended_fixes) >= 1
    assert fixes.recommended_fixes[0].package == "typing-extensions"
    assert fixes.recommended_fixes[0].blast_radius_count == 9
