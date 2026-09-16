"""
Regression and verification test suite for Phase A:
- Data model formalization
- Graph versioning & snapshot reproducibility
- Configurable centrality weighting
- Hidden critical detection
- Full 64-node error audit
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetcher import load_cached_graph
from src.graph_builder import build_dependency_graph, compute_structural_metrics
from src.scoring import compute_composite_criticality, generate_explanation
from src.simulator import simulate_compromise
from src.models import WeightingConfig


def run_phase_a_verification():
    raw = load_cached_graph()
    meta = raw.get("metadata", {})
    print(f"[Item 2] Snapshot verified: ID={meta.get('snapshot_id')}, schema={meta.get('schema_version')}")
    assert "snapshot_id" in meta
    assert meta.get("schema_version") == "1.0"

    G = build_dependency_graph(raw)
    metrics = compute_structural_metrics(G)
    max_in = max(m["in_degree"] for m in metrics.values())
    max_tr = max(m["transitive_dependents_count"] for m in metrics.values())

    # Item 1 & 3: Default Weights Verification
    def_scores = {n: compute_composite_criticality(n, metrics[n], max_in, max_tr) for n in G.nodes()}
    print(f"[Item 1 & 3] Default scores: debug={def_scores['debug'].score}, ms={def_scores['ms'].score}, mime-types={def_scores['mime-types'].score}")
    assert def_scores["debug"].score == 79.5
    assert def_scores["ms"].score == 60.1
    assert def_scores["mime-types"].score == 58.6
    assert def_scores["dotenv"].score == 5.2

    # Item 4: Hidden Critical Flag Verification
    hidden_crit_nodes = [n for n, sc in def_scores.items() if sc.is_hidden_critical]
    print(f"[Item 4] Hidden Critical packages ({len(hidden_crit_nodes)} total): {hidden_crit_nodes}")
    assert "debug" in hidden_crit_nodes
    assert "ms" in hidden_crit_nodes
    assert "mime-types" in hidden_crit_nodes
    assert "depd" in hidden_crit_nodes
    assert "on-finished" in hidden_crit_nodes

    # Item 3: Alternative Weighting Configs
    test_configs = [
        WeightingConfig(0.50, 0.30, 0.20),
        WeightingConfig(0.10, 0.70, 0.20),
        WeightingConfig(0.80, 0.10, 0.10),
    ]
    for cfg in test_configs:
        scores = {n: compute_composite_criticality(n, metrics[n], max_in, max_tr, weight_config=cfg) for n in G.nodes()}
        assert len(scores) == 64
        for n, sc in scores.items():
            assert 0.0 <= sc.score <= 100.0
            assert sc.tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    print("[Item 3] Dynamic re-weighting verified across alternative splits.")

    # Full 64-node error audit
    errors = []
    for n in G.nodes():
        try:
            sc = def_scores[n]
            exp = generate_explanation(n, sc, metrics[n])
            if not exp or not isinstance(exp, str):
                errors.append((n, "empty/invalid explanation"))
            sim = simulate_compromise(G, n)
            if sim.affected_count == 0:
                errors.append((n, "zero affected count"))
            if n not in sim.affected_nodes:
                errors.append((n, "root not in affected nodes"))
        except Exception as e:
            errors.append((n, str(e)))

    print(f"Total Nodes Audited: {len(G.nodes())}, Errors: {len(errors)}")
    assert len(errors) == 0, f"Errors found: {errors}"
    print("PHASE A REGRESSION TEST SUITE PASSED WITH 0 ERRORS!")


if __name__ == "__main__":
    run_phase_a_verification()
