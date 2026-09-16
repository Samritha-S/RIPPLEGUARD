import os
import sys
import time
import random
import networkx as nx

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.fetcher import load_cached_graph, load_cached_pypi_graph
from src.graph_builder import build_dependency_graph

def run_benchmark():
    print("=== BENCHMARKING BETWEENNESS CENTRALITY ===", flush=True)
    
    # 1. 64-node npm
    npm_data = load_cached_graph()
    G_npm = build_dependency_graph(npm_data)
    t0 = time.perf_counter()
    bc_npm = nx.betweenness_centrality(G_npm)
    t_npm_ms = (time.perf_counter() - t0) * 1000.0
    print(f"1. NPM ({G_npm.number_of_nodes()} nodes, {G_npm.number_of_edges()} edges): {t_npm_ms:.3f} ms ({t_npm_ms/1000.0:.4f} s)", flush=True)

    # 2. 35-node PyPI
    pypi_data = load_cached_pypi_graph()
    G_pypi = build_dependency_graph(pypi_data)
    t0 = time.perf_counter()
    bc_pypi = nx.betweenness_centrality(G_pypi)
    t_pypi_ms = (time.perf_counter() - t0) * 1000.0
    print(f"2. PyPI ({G_pypi.number_of_nodes()} nodes, {G_pypi.number_of_edges()} edges): {t_pypi_ms:.3f} ms ({t_pypi_ms/1000.0:.4f} s)", flush=True)

    # 3. 10,000-node synthetic DAG (identical generator to scripts/stress_test.py)
    n_nodes = 10000
    random.seed(42)
    print(f"Generating synthetic graph with {n_nodes} nodes...", flush=True)
    G_synth = nx.DiGraph()
    for i in range(n_nodes):
        G_synth.add_node(f"pkg_{i}")
    for i in range(n_nodes):
        k = random.randint(1, 6)
        window = min(n_nodes, i + 60)
        if window > i + 1:
            targets = random.sample(range(i + 1, window), min(k, window - (i + 1)))
            for t in targets:
                G_synth.add_edge(f"pkg_{i}", f"pkg_{t}")
    n_edges = G_synth.number_of_edges()
    print(f"Synthetic DAG generated: {n_nodes} nodes, {n_edges} edges.", flush=True)

    print(f"Running nx.betweenness_centrality on {n_nodes} nodes...", flush=True)
    t0 = time.perf_counter()
    bc_synth = nx.betweenness_centrality(G_synth)
    t_synth_s = time.perf_counter() - t0
    print(f"3. Synthetic 10k ({n_nodes} nodes, {n_edges} edges): {t_synth_s:.3f} s ({t_synth_s*1000.0:.1f} ms)", flush=True)

if __name__ == "__main__":
    run_benchmark()
