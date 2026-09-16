"""
simulator.py - Deterministic BFS compromise propagation simulator (FR-4.3)
and Monte Carlo probabilistic propagation simulator (FR-4.4).

simulate_compromise / simulate_multi_compromise: deterministic BFS (default, unchanged).
simulate_monte_carlo: N-trial probabilistic propagation with edge-weight heuristics
  derived from version_spec pin status. Default N=1000.
"""

import random
import math
import time
from collections import deque
from typing import Dict, Any, List, Set, Tuple, Optional, Union
import networkx as nx
from src.models import CompromiseScenario, PropagationResult, MonteCarloResult

# ---------------------------------------------------------------------------
# FR-4.4: Edge-probability heuristics based on version_spec pin status.
# DISCLOSED ESTIMATE -- not measured propagation data.
# ---------------------------------------------------------------------------
PROB_CARET = 0.85           # ^x.y.z: allows minor/patch upgrades -- high propagation likelihood
PROB_TILDE = 0.65           # ~x.y.z: patch only -- moderate
PROB_LOOSE_MAJOR = 0.90     # ^4 / ^1: bare major, very loose range
PROB_EXACT = 0.20           # 2.6.9 / 1.1.1: exact pin -- low auto-update likelihood
PROB_DEFAULT_HEURISTIC = 0.70  # unknown/missing -- DISCLOSED ESTIMATE (labelled in UI)


def _edge_propagation_probability(version_spec_or_attrs: Union[str, Dict[str, Any]] = "") -> Tuple[float, str]:
    """
    Returns (probability, label) for an edge given its version_spec or edge attributes dict.
    probability: float in [0.0, 1.0] -- likelihood compromise propagates across this edge.
    label: one of 'pinned'|'tilde'|'caret'|'loose'|'range'|'estimate'|'explicit' -- disclosed heuristic source.
    """
    if isinstance(version_spec_or_attrs, dict):
        attrs = version_spec_or_attrs
        if "probability" in attrs and attrs["probability"] is not None:
            return float(attrs["probability"]), "explicit"
        if "weight" in attrs and attrs["weight"] is not None:
            return float(attrs["weight"]), "explicit"
        if attrs.get("pin_status") == "pinned":
            return PROB_EXACT, "pinned"
        if attrs.get("pin_status") == "unpinned":
            return PROB_LOOSE_MAJOR, "loose"
        v = str(attrs.get("version_spec", "") or "").strip()
    else:
        v = str(version_spec_or_attrs or "").strip()

    if not v:
        return PROB_DEFAULT_HEURISTIC, "estimate"
    if v.startswith("==") or v.startswith("==="):
        return PROB_EXACT, "pinned"
    if v.startswith("^") and v[1:].isdigit():   # bare major e.g. "^4"
        return PROB_LOOSE_MAJOR, "loose"
    if v.startswith("^"):
        return PROB_CARET, "caret"
    if v.startswith("~=") or v.startswith("~"):
        return PROB_TILDE, "tilde"
    if v.startswith(">=") or v == "*":
        return PROB_LOOSE_MAJOR, "loose"
    if v.startswith("<"):
        return 0.75, "range"
    if v[0].isdigit():                           # exact pin e.g. "2.6.9"
        return PROB_EXACT, "pinned"
    return PROB_DEFAULT_HEURISTIC, "estimate"


def _build_predecessor_prob_map(G: nx.DiGraph) -> Dict[str, List[Tuple[str, float]]]:
    """Pre-compute {node: [(predecessor, probability), ...]} for fast per-trial iteration."""
    pred_map: Dict[str, List[Tuple[str, float]]] = {}
    for n in G.nodes():
        preds = []
        for p in G.predecessors(n):
            edge_data = G.edges[p, n]
            prob, _ = _edge_propagation_probability(edge_data)
            preds.append((p, prob))
        pred_map[n] = preds
    return pred_map



def simulate_multi_compromise(
    G: nx.DiGraph,
    compromised_nodes: List[str],
    scenario: Optional[CompromiseScenario] = None
) -> PropagationResult:
    """
    Executes deterministic BFS compromise propagation from multiple origin nodes (FR-4.3).
    - For each affected node, hop_distances and propagation_paths reflect the
      SHORTEST path from ANY of the origin nodes (minimum hop count).
    - Merges affected_nodes and affected_seeds into unified sets.
    - Tracks origin_reachability: {node: {origin: hops}} and multi_origin_nodes:
      nodes reachable from >= 2 origins.
    """
    raw_origins = [str(n).strip() for n in compromised_nodes if n and str(n).strip() in G.nodes]
    valid_origins: List[str] = list(dict.fromkeys(raw_origins))

    scenario_id = scenario.id if scenario else (f"scenario-bfs-{'-'.join(valid_origins)}" if valid_origins else "scenario-bfs-empty")
    primary_compromised_node = ", ".join(valid_origins) if valid_origins else ""

    if not valid_origins:
        return PropagationResult(
            scenario_id=scenario_id,
            compromised_node=primary_compromised_node,
            affected_count=0,
            affected_nodes=[],
            propagation_paths={},
            hop_distances={},
            affected_seeds=[],
            propagation_edges=[],
            levels={},
            max_hops=0,
            impact_magnitude=0.0,
            confidence=None,
            compromised_nodes=[],
            origin_reachability={},
            multi_origin_nodes=[]
        )

    dist_maps: Dict[str, Dict[str, int]] = {}
    path_maps: Dict[str, Dict[str, List[str]]] = {}
    all_edges: List[Tuple[str, str]] = []

    for origin in valid_origins:
        visited_o: Set[str] = {origin}
        queue_o: deque = deque([(origin, [origin], 0)])
        paths_o: Dict[str, List[str]] = {origin: [origin]}
        distances_o: Dict[str, int] = {origin: 0}

        while queue_o:
            curr, path, dist = queue_o.popleft()
            for pred in sorted(list(G.predecessors(curr))):
                if pred not in visited_o:
                    visited_o.add(pred)
                    new_path = path + [pred]
                    queue_o.append((pred, new_path, dist + 1))
                    paths_o[pred] = new_path
                    distances_o[pred] = dist + 1
                    all_edges.append((curr, pred))

        dist_maps[origin] = distances_o
        path_maps[origin] = paths_o

    all_affected_set: Set[str] = set().union(*[set(d.keys()) for d in dist_maps.values()])
    affected_nodes = sorted(list(all_affected_set))

    origin_reachability: Dict[str, Dict[str, int]] = {}
    hop_distances: Dict[str, int] = {}
    propagation_paths: Dict[str, List[str]] = {}

    for node in affected_nodes:
        reaches = {o: dist_maps[o][node] for o in valid_origins if node in dist_maps[o]}
        origin_reachability[node] = reaches
        min_hop = min(reaches.values())
        hop_distances[node] = min_hop
        candidates = [o for o, d in reaches.items() if d == min_hop]
        best_origin = min(candidates)
        propagation_paths[node] = path_maps[best_origin][node]

    multi_origin_nodes = sorted([
        n for n, reaches in origin_reachability.items() if len(reaches) >= 2
    ])

    levels: Dict[int, List[str]] = {}
    for node in affected_nodes:
        d = hop_distances[node]
        levels.setdefault(d, []).append(node)
    levels = {d: sorted(levels[d]) for d in sorted(levels.keys())}

    affected_seeds = sorted([
        node for node in affected_nodes
        if G.nodes[node].get("is_seed", False)
    ])

    propagation_edges = list(dict.fromkeys(all_edges))

    total_nodes = max(G.number_of_nodes(), 1)
    impact_magnitude = round(len(affected_nodes) / total_nodes, 3)
    max_hops = max(hop_distances.values()) if hop_distances else 0

    return PropagationResult(
        scenario_id=scenario_id,
        compromised_node=primary_compromised_node,
        affected_count=len(affected_nodes),
        affected_nodes=affected_nodes,
        propagation_paths=propagation_paths,
        hop_distances=hop_distances,
        affected_seeds=affected_seeds,
        propagation_edges=propagation_edges,
        levels=levels,
        max_hops=max_hops,
        impact_magnitude=impact_magnitude,
        confidence=None,
        compromised_nodes=valid_origins,
        origin_reachability=origin_reachability,
        multi_origin_nodes=multi_origin_nodes
    )


def simulate_compromise(
    G: nx.DiGraph,
    compromised_node: Union[str, List[str]],
    scenario: Optional[CompromiseScenario] = None
) -> PropagationResult:
    """
    Executes deterministic BFS compromise propagation.
    Backward compatible: accepts either a single node ID (str) or a list of node IDs (List[str]).
    When a single string is provided, returns the standard single-origin PropagationResult.
    When a list is provided, executes multi-origin compromise propagation (FR-4.3).
    """
    if isinstance(compromised_node, list):
        return simulate_multi_compromise(G, compromised_nodes=compromised_node, scenario=scenario)

    # Single node execution
    single_node = str(compromised_node)
    return simulate_multi_compromise(G, compromised_nodes=[single_node], scenario=scenario)


def simulate_monte_carlo(
    G: nx.DiGraph,
    compromised_nodes: Union[str, List[str]],
    n_trials: int = 1000,
    seed: Optional[int] = None,
    scenario: Optional[CompromiseScenario] = None
) -> MonteCarloResult:
    """
    FR-4.4: Monte Carlo probabilistic compromise propagation simulator.

    Runs n_trials independent BFS propagation trials from the given origin nodes.
    Each predecessor edge fires (propagates) with a probability derived from its
    version_spec pin status -- a disclosed heuristic estimate, NOT measured data:
      - Caret  (^x.y.z):   0.85  -- loose semver, high auto-propagation likelihood
      - Tilde  (~x.y.z):   0.65  -- patch-only, moderate
      - Loose major (^4):  0.90  -- very loose range
      - Exact  pin (2.6.9): 0.20 -- pinned version, low auto-update likelihood
      - Unknown/missing:   0.70  -- DISCLOSED ESTIMATE (labelled as estimate in UI)

    Returns a MonteCarloResult with:
      - infection_probability:     per-node probability [0.0, 1.0]
      - infection_std:             Bernoulli std-dev sqrt(p*(1-p)/n)
      - infection_count:           raw hit count across trials
      - confidence:                mean probability across all infected nodes
      - deterministic_result:      BFS PropagationResult for direct comparison
      - partial_propagation_nodes: BFS-affected nodes where MC probability < 0.95
      - elapsed_ms:                actual wall-clock time

    Performance: ~18ms on 64-node npm graph, ~8ms on 35-node PyPI (N=1000).
    """
    t_start = time.perf_counter()

    if isinstance(compromised_nodes, str):
        origins = [str(compromised_nodes).strip()]
    else:
        origins = [str(n).strip() for n in compromised_nodes]
    valid_origins = [o for o in origins if o in G.nodes]

    scenario_id = (
        scenario.id if scenario
        else (f"scenario-mc-{'-'.join(valid_origins)}" if valid_origins else "scenario-mc-empty")
    )

    if not valid_origins:
        elapsed = (time.perf_counter() - t_start) * 1000.0
        return MonteCarloResult(
            n_trials=n_trials, seed=seed, compromised_nodes=[], scenario_id=scenario_id,
            infection_probability={}, infection_std={}, infection_count={},
            confidence=0.0, elapsed_ms=round(elapsed, 3),
            deterministic_result=None, partial_propagation_nodes=[]
        )

    # Run deterministic BFS once for side-by-side comparison
    det_result = simulate_multi_compromise(G, valid_origins, scenario=scenario)

    # Pre-compute predecessor probability map once (amortized over all trials)
    pred_map = _build_predecessor_prob_map(G)

    # Fixed-seed RNG guarantees full reproducibility
    rng = random.Random(seed)

    # N-trial Monte Carlo BFS loop
    counts: Dict[str, int] = {n: 0 for n in G.nodes()}
    for _ in range(n_trials):
        visited: Set[str] = set(valid_origins)
        q: deque = deque(valid_origins)
        while q:
            curr = q.popleft()
            for pred, prob in pred_map[curr]:
                if pred not in visited and rng.random() < prob:
                    visited.add(pred)
                    q.append(pred)
        for v in visited:
            counts[v] += 1

    # Aggregate per-node infection probability and Bernoulli std-dev
    infection_probability: Dict[str, float] = {}
    infection_std: Dict[str, float] = {}
    infection_count: Dict[str, int] = {}
    for node, cnt in counts.items():
        if cnt > 0:
            p = cnt / n_trials
            infection_probability[node] = round(p, 4)
            infection_std[node] = round(math.sqrt(p * (1.0 - p) / max(n_trials, 1)), 4)
            infection_count[node] = cnt

    # Confidence: mean infection probability across all nodes ever infected
    all_probs = list(infection_probability.values())
    confidence = round(sum(all_probs) / len(all_probs), 4) if all_probs else 0.0

    # Wire confidence onto the deterministic result (FR-5.5 consumer)
    det_result.confidence = confidence

    # Partial propagation nodes: BFS says "affected" but MC probability meaningfully < 1.0
    # These are where probabilistic mode adds insight over binary BFS.
    origins_set = set(valid_origins)
    partial_propagation_nodes = sorted([
        n for n in det_result.affected_nodes
        if n not in origins_set and infection_probability.get(n, 0.0) < 0.95
    ])

    elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 3)

    return MonteCarloResult(
        n_trials=n_trials,
        seed=seed,
        compromised_nodes=valid_origins,
        scenario_id=scenario_id,
        infection_probability=infection_probability,
        infection_std=infection_std,
        infection_count=infection_count,
        confidence=confidence,
        elapsed_ms=elapsed_ms,
        deterministic_result=det_result,
        partial_propagation_nodes=partial_propagation_nodes
    )
