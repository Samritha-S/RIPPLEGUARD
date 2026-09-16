"""
Unit tests for FRD typed dataclass models in src/models.py
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import (
    PackageNode,
    DependencyEdge,
    VulnerabilityRecord,
    WeightingConfig,
    CriticalityScore,
    CompromiseScenario,
    PropagationResult,
    MitigationRecommendation
)


def test_models_instantiation_and_dict_compatibility():
    # PackageNode
    node = PackageNode(id="express", name="express", version="5.2.1", is_seed=True)
    assert node.id == "express"
    assert node["id"] == "express"
    assert node.get("version") == "5.2.1"
    assert "name" in node

    # DependencyEdge
    edge = DependencyEdge(source="express", target="debug", version_constraint="^4.3.4")
    assert edge.source == "express"
    assert edge["target"] == "debug"

    # VulnerabilityRecord
    vuln = VulnerabilityRecord(id="CVE-2024-0001", severity=7.5, is_curated=True)
    assert vuln.severity == 7.5
    assert vuln["id"] == "CVE-2024-0001"

    # WeightingConfig
    cfg = WeightingConfig(0.35, 0.40, 0.25)
    assert round(cfg.weight_cvss + cfg.weight_transitive + cfg.weight_indegree, 2) == 1.0

    # CriticalityScore
    score = CriticalityScore(
        node_id="debug",
        composite_score=79.5,
        structural_subscore=60.0,
        vulnerability_subscore=19.5,
        weighting_config=cfg,
        tier="CRITICAL",
        tier_color="#e63946",
        cvss=5.3,
        is_curated_cve=True,
        is_hidden_critical=True
    )
    assert score.score == 79.5
    assert score["score"] == 79.5
    assert score.is_hidden_critical is True
    assert score["is_hidden_critical"] is True

    # CompromiseScenario
    scen = CompromiseScenario(id="scen-01", seed_node="debug")
    assert scen.seed_node == "debug"
    assert scen["id"] == "scen-01"

    # PropagationResult
    prop = PropagationResult(
        scenario_id="scen-01",
        compromised_node="debug",
        affected_count=10,
        affected_nodes=["debug", "express"],
        propagation_paths={"express": ["debug", "express"]},
        hop_distances={"express": 1},
        affected_seeds=["express"],
        propagation_edges=[("debug", "express")],
        levels={0: ["debug"], 1: ["express"]},
        max_hops=1,
        impact_magnitude=0.156
    )
    assert prop.affected_count == 10
    assert prop["affected_count"] == 10
    assert prop.impact_magnitude == 0.156

    # MitigationRecommendation
    mit = MitigationRecommendation(
        target_node="debug",
        risk_tier="CRITICAL",
        action_type="PIN_HASH",
        description="Pin digest hash in package-lock.json",
        estimated_impact="HIGH",
        estimated_effort="LOW"
    )
    assert mit.action_type == "PIN_HASH"
    assert mit["risk_tier"] == "CRITICAL"


if __name__ == "__main__":
    test_models_instantiation_and_dict_compatibility()
    print("All model tests passed successfully!")
