"""
Verification script for RippleGuard core engine:
- Graph building
- Metrics computation
- Criticality scoring & ranking
- Plain-language explanation generation
- BFS compromise simulation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetcher import get_cached_or_fetch_graph
from src.graph_builder import build_dependency_graph, compute_structural_metrics
from src.scoring import compute_composite_criticality, generate_explanation, get_mitigations_for_tier
from src.simulator import simulate_compromise


def run_tests():
    data = get_cached_or_fetch_graph()
    G = build_dependency_graph(data)
    metrics = compute_structural_metrics(G)

    max_in_deg = max(m["in_degree"] for m in metrics.values())
    max_trans = max(m["transitive_dependents_count"] for m in metrics.values())

    print(f"Total Nodes: {G.number_of_nodes()}, Total Edges: {G.number_of_edges()}")
    print(f"Max in-degree: {max_in_deg}, Max transitive dependents: {max_trans}")

    scores = {}
    for node, m in metrics.items():
        scores[node] = compute_composite_criticality(node, m, max_in_deg, max_trans)

    ranked = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    print("\n--- TOP 10 HIGHEST CRITICALITY PACKAGES ---")
    for node, sc in ranked[:10]:
        m = metrics[node]
        print(f"{node:<20} | Score: {sc['score']:>5.1f} | Tier: {sc['tier']:<8} | CVSS: {sc['cvss']:>3.1f} | InDeg: {m['in_degree']:>2} | Transitive: {m['transitive_dependents_count']:>2} | Seeds: {m['affected_seeds']}")

    print("\n--- EXPLANATION EXAMPLES ---")
    for test_pkg in ["debug", "follow-redirects", "dotenv"]:
        print(f"\n[{test_pkg.upper()}]")
        print(generate_explanation(test_pkg, scores[test_pkg], metrics[test_pkg]))
        print("Mitigations:")
        for mit in get_mitigations_for_tier(scores[test_pkg]["tier"]):
            print(f"  - {mit}")

    # Regression check across EVERY node
    print("\n--- RUNNING COMPLETE REGRESSION ACROSS ALL NODES ---")
    node_errors = []
    for node in G.nodes():
        m = metrics[node]
        sc = scores[node]
        if not (0.0 <= sc["score"] <= 100.0):
            node_errors.append((node, "Score out of range", sc["score"]))
        exp = generate_explanation(node, sc, m)
        if not exp or not isinstance(exp, str):
            node_errors.append((node, "Invalid explanation", exp))
        mits = get_mitigations_for_tier(sc["tier"])
        if not mits or len(mits) < 2:
            node_errors.append((node, "Missing mitigations", mits))
        sim = simulate_compromise(G, node)
        if sim["affected_count"] == 0:
            node_errors.append((node, "Zero affected count", sim))

    if node_errors:
        print(f"FAILED: Found {len(node_errors)} errors across nodes!")
        for err in node_errors:
            print("  -", err)
    else:
        print(f"PASSED: All {G.number_of_nodes()} nodes verified without errors, nulls, or invalid scores.")

    print("\n--- COMPROMISE SIMULATION ON 'debug' ---")
    sim = simulate_compromise(G, "debug")
    print(f"Compromised Root: {sim['compromised_node']}")
    print(f"Total Affected: {sim['affected_count']}")
    print(f"Affected Seeds: {sim['affected_seeds']}")
    print(f"Max Hops: {sim['max_hops']}")
    print("Propagation Paths to Affected Seeds:")
    for s in sim["affected_seeds"]:
        print(f"  Path to {s}: {' -> '.join(sim['propagation_paths'][s])}")


if __name__ == "__main__":
    run_tests()
