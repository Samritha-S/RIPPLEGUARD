"""
test_fetcher.py - Unit tests for FR-1.4 (Real Package Metadata) and FR-2.3 (Configurable Depth).
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetcher import load_cached_graph, resolve_dependency_tree, DEFAULT_SEEDS


def test_fr14_real_package_metadata():
    """Verify FR-1.4: Real package metadata is present on cached nodes without fabrication."""
    data = load_cached_graph()
    nodes = {n["id"]: n for n in data["nodes"]}

    # Verify debug metadata
    debug = nodes.get("debug")
    assert debug is not None, "debug node missing"
    assert debug["version"] == "4.4.3"
    assert debug["license"] == "MIT"
    assert debug["publish_date"] is not None and "2025" in debug["publish_date"]
    assert isinstance(debug["maintainers"], list) and len(debug["maintainers"]) >= 2
    assert debug["downloads"] is None, "downloads should be None (not fabricated)"

    # Verify express metadata
    express = nodes.get("express")
    assert express is not None, "express node missing"
    assert express["version"] == "5.2.1"
    assert express["license"] == "MIT"
    assert express["publish_date"] is not None and "2025" in express["publish_date"]
    assert isinstance(express["maintainers"], list) and len(express["maintainers"]) >= 2
    assert express["is_seed"] is True
    assert express["downloads"] is None

    # Verify mime-types metadata
    mime = nodes.get("mime-types")
    assert mime is not None, "mime-types node missing"
    assert mime["license"] == "MIT"
    assert mime["publish_date"] is not None
    assert isinstance(mime["maintainers"], list)
    assert mime["downloads"] is None


def test_fr23_configurable_crawl_depth():
    """Verify FR-2.3: Crawl depth parameter is fully functional and traverses deeper levels."""
    # Test depth 0: only seed packages
    d0_tree = resolve_dependency_tree(seeds=["express"], max_depth=0)
    assert len(d0_tree["nodes"]) == 1
    assert len(d0_tree["edges"]) == 0

    # Test depth 1: express + its direct dependencies
    d1_tree = resolve_dependency_tree(seeds=["express"], max_depth=1)
    assert len(d1_tree["nodes"]) > 1
    assert len(d1_tree["edges"]) > 0
    # Confirm no nodes exceed depth 1
    assert all(n["depth"] <= 1 for n in d1_tree["nodes"])


if __name__ == "__main__":
    test_fr14_real_package_metadata()
    print("test_fr14_real_package_metadata PASSED")
    test_fr23_configurable_crawl_depth()
    print("test_fr23_configurable_crawl_depth PASSED")
