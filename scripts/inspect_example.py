import os
import sys
import networkx as nx

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.fetcher import load_cached_graph
from src.graph_builder import build_dependency_graph, compute_structural_metrics

G = build_dependency_graph(load_cached_graph())
metrics = compute_structural_metrics(G)
bc = nx.betweenness_centrality(G)

print(f"{'Package':<16} | {'In-Deg':<8} | {'Transitive':<10} | {'Betweenness':<12}")
print("-" * 52)
for n, val in sorted(bc.items(), key=lambda x: x[1], reverse=True)[:10]:
    m = metrics[n]
    print(f"{n:<16} | {m['in_degree']:<8} | {m['transitive_dependents_count']:<10} | {val:<12.6f}")

print("\nCompare with highest in-degree / transitive nodes:")
for n in ['debug', 'mime-types', 'ms', 'http-errors', 'send']:
    m = metrics[n]
    print(f"{n:<16} | {m['in_degree']:<8} | {m['transitive_dependents_count']:<10} | {bc[n]:<12.6f}")
