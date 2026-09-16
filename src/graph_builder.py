"""
graph_builder.py - Constructs a NetworkX DiGraph from cached dependency data
and computes structural centrality & blast radius metrics.
"""

import networkx as nx
from typing import Dict, Any, Tuple, Set


def build_dependency_graph(graph_data: Dict[str, Any]) -> nx.DiGraph:
    """
    Builds a directed NetworkX graph where edge A -> B means 'A depends on B'.
    Node attributes include id, version, description, depth, and is_seed.
    """
    G = nx.DiGraph()

    # Add nodes with metadata
    for node in graph_data.get("nodes", []):
        G.add_node(
            node["id"],
            id=node["id"],
            name=node.get("name", node["id"]),
            ecosystem=node.get("ecosystem", "npm"),
            version=node.get("version", "unknown"),
            publish_date=node.get("publish_date"),
            maintainers=node.get("maintainers"),
            downloads=node.get("downloads"),
            license=node.get("license"),
            known_cves=node.get("known_cves", []),
            description=node.get("description", ""),
            depth=node.get("depth", 0),
            is_seed=node.get("is_seed", False)
        )

    # Add edges: source -> target ("source depends on target")
    for edge in graph_data.get("edges", []):
        src = edge["source"]
        tgt = edge["target"]
        version_spec = edge.get("version_spec", "")
        # Ensure target node exists even if it was at max depth leaf
        if not G.has_node(tgt):
            src_depth = G.nodes[src].get("depth", 1) if G.has_node(src) else 1
            G.add_node(
                tgt,
                id=tgt,
                name=tgt,
                ecosystem="npm",
                version="unresolved",
                publish_date=None,
                maintainers=None,
                downloads=None,
                license=None,
                known_cves=[],
                description="Transitive leaf dependency",
                depth=src_depth + 1,
                is_seed=False
            )
        G.add_edge(src, tgt, version_spec=version_spec)

    return G


BETWEENNESS_MAX_NODES = 500


def compute_structural_metrics(
    G: nx.DiGraph,
    betweenness_threshold: int = BETWEENNESS_MAX_NODES
) -> Dict[str, Dict[str, Any]]:
    """
    Computes structural metrics for every node:
    - in_degree: direct dependents (packages that directly depend on this node)
    - out_degree: direct dependencies (packages this node depends on)
    - transitive_dependents_count: count of all nodes that depend on this node
      (reachable by traversing edges backwards, i.e. nx.ancestors(G, node))
    - transitive_dependents: set of package names
    - affected_seed_count: number of top-level seed packages that depend on this node
    - betweenness_centrality: fraction of all shortest paths passing through this node (0-1)
    - betweenness_skipped: whether betweenness calculation was skipped due to node count threshold

    Optimized for NFR-2:
    - Replaces per-node O(V * (V + E)) nx.ancestors calls with topological order dynamic
      programming, reducing traversal from quadratic to roughly O(V + E) for DAGs.
    - Explicit cycle handling (EDGE-2): if a directed cycle is present, gracefully falls back
      to Strongly Connected Components (SCC) condensation so cyclic graphs cannot crash or
      infinite-loop and remain bit-for-bit identical to nx.ancestors.
    """
    try:
        # Fast path for DAGs: topological order dynamic programming
        all_ancestors: Dict[str, Set[str]] = {}
        for n in nx.topological_sort(G):
            s: Set[str] = set()
            for p in G.predecessors(n):
                s.add(p)
                s.update(all_ancestors[p])
            all_ancestors[n] = s
    except nx.NetworkXUnfeasible:
        # Cyclic fallback via Strongly Connected Components condensation (guaranteed DAG)
        C = nx.condensation(G)
        comp_ancestors: Dict[int, Set[int]] = {}
        for c in nx.topological_sort(C):
            s_comp: Set[int] = set()
            for p in C.predecessors(c):
                s_comp.add(p)
                s_comp.update(comp_ancestors[p])
            comp_ancestors[c] = s_comp
        node_to_comp = C.graph["mapping"]
        comp_members = {c: set(C.nodes[c]["members"]) for c in C.nodes()}
        all_ancestors = {}
        for node in G.nodes():
            c = node_to_comp[node]
            ans: Set[str] = set()
            for anc_c in comp_ancestors[c]:
                ans.update(comp_members[anc_c])
            ans.update(comp_members[c] - {node})
            all_ancestors[node] = ans

    seed_nodes: Set[str] = {n for n in G.nodes() if G.nodes[n].get("is_seed", False)}
    metrics: Dict[str, Dict[str, Any]] = {}

    # FR-3.1: Size-gated Betweenness Centrality
    # Brandes' algorithm is O(V * E); fast (< 10ms) on demo graphs (< 500 nodes), but slow (> 5 min) at 10k+.
    node_count = G.number_of_nodes()
    if node_count <= betweenness_threshold:
        bc: Dict[str, float] = nx.betweenness_centrality(G)
        betweenness_skipped = False
    else:
        bc = {n: 0.0 for n in G.nodes()}
        betweenness_skipped = True

    for node in G.nodes():
        direct_dependents = list(G.predecessors(node))  # nodes A where A -> node
        direct_dependencies = list(G.successors(node))   # nodes B where node -> B
        transitive_dependents = all_ancestors[node]

        affected_seeds = set(transitive_dependents & seed_nodes)
        if node in seed_nodes:
            affected_seeds.add(node)
        sorted_seeds = sorted(list(affected_seeds))

        metrics[node] = {
            "in_degree": len(direct_dependents),
            "out_degree": len(direct_dependencies),
            "direct_dependents": direct_dependents,
            "direct_dependencies": direct_dependencies,
            "transitive_dependents_count": len(transitive_dependents),
            "transitive_dependents": sorted(list(transitive_dependents)),
            "affected_seed_count": len(sorted_seeds),
            "affected_seeds": sorted_seeds,
            "is_seed": G.nodes[node].get("is_seed", False),
            "version": G.nodes[node].get("version", "unknown"),
            "description": G.nodes[node].get("description", ""),
            "name": G.nodes[node].get("name", node),
            "ecosystem": G.nodes[node].get("ecosystem", "npm"),
            "publish_date": G.nodes[node].get("publish_date"),
            "maintainers": G.nodes[node].get("maintainers"),
            "downloads": G.nodes[node].get("downloads"),
            "license": G.nodes[node].get("license"),
            "known_cves": G.nodes[node].get("known_cves", []),
            "betweenness_centrality": bc.get(node, 0.0),
            "betweenness_skipped": betweenness_skipped
        }

    return metrics

