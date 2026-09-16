"""
models.py - Formal typed dataclass entities for RippleGuard.
Matching the FRD data model specifications with dictionary compatibility.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone


class DictCompatible:
    """Provides dictionary-like subscripting and conversion for backward compatibility."""

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def keys(self):
        return asdict(self).keys()

    def values(self):
        return asdict(self).values()

    def items(self):
        return asdict(self).items()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PackageNode(DictCompatible):
    """Represents a software package node in the supply chain dependency graph."""
    id: str
    name: str
    ecosystem: str = "npm"
    version: Optional[str] = None
    publish_date: Optional[str] = None
    maintainers: Optional[List[str]] = None
    downloads: Optional[int] = None
    known_cves: List[str] = field(default_factory=list)
    license: Optional[str] = None
    description: Optional[str] = None
    depth: int = 0
    is_seed: bool = False


@dataclass
class DependencyEdge(DictCompatible):
    """Represents a directed dependency edge (source depends on target)."""
    source: str
    target: str
    version_constraint: str = "*"
    dependency_type: str = "prod"
    pin_status: Optional[str] = None


@dataclass
class VulnerabilityRecord(DictCompatible):
    """Represents an associated vulnerability or CVE record."""
    id: str
    severity: float  # CVSS 0.0 - 10.0
    exploit_maturity: Optional[str] = None
    patch_availability: Optional[str] = None
    affected_version_range: Optional[str] = None
    is_curated: bool = False


@dataclass
class WeightingConfig(DictCompatible):
    """Configurable weights for composite criticality scoring."""
    weight_cvss: float = 0.35
    weight_transitive: float = 0.40
    weight_indegree: float = 0.25
    weight_betweenness: float = 0.0

    def normalize(self) -> "WeightingConfig":
        total = self.weight_cvss + self.weight_transitive + self.weight_indegree + self.weight_betweenness
        if total <= 0:
            return WeightingConfig(0.35, 0.40, 0.25, 0.0)
        return WeightingConfig(
            weight_cvss=self.weight_cvss / total,
            weight_transitive=self.weight_transitive / total,
            weight_indegree=self.weight_indegree / total,
            weight_betweenness=self.weight_betweenness / total
        )


@dataclass
class CriticalityScore(DictCompatible):
    """Calculated composite criticality score and risk tier."""
    node_id: str
    composite_score: float
    structural_subscore: float
    vulnerability_subscore: float
    weighting_config: WeightingConfig
    tier: str
    tier_color: str
    cvss: float
    is_curated_cve: bool = False
    is_hidden_critical: bool = False
    in_degree: int = 0
    transitive_dependents: int = 0
    norm_cvss: float = 0.0
    norm_in_deg: float = 0.0
    norm_trans: float = 0.0
    severity_source: str = "curated"
    betweenness_centrality: float = 0.0
    norm_between: float = 0.0
    norm_betweenness: float = 0.0

    # Alias score property for backwards compatibility with score_data["score"]
    @property
    def score(self) -> float:
        return self.composite_score


@dataclass
class CompromiseScenario(DictCompatible):
    """Definition of a compromise simulation scenario."""
    id: str
    seed_node: str
    propagation_model: str = "deterministic_bfs"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PropagationResult(DictCompatible):
    """Outcome of compromise propagation simulation across the graph."""
    scenario_id: str
    compromised_node: str
    affected_count: int
    affected_nodes: List[str]
    propagation_paths: Dict[str, List[str]]
    hop_distances: Dict[str, int]
    affected_seeds: List[str]
    propagation_edges: List[Tuple[str, str]]
    levels: Dict[int, List[str]]
    max_hops: int
    impact_magnitude: float = 0.0
    confidence: Optional[float] = None  # Populated in Phase D
    compromised_nodes: List[str] = field(default_factory=list)  # FR-4.3: All origin nodes
    origin_reachability: Dict[str, Dict[str, int]] = field(default_factory=dict)  # FR-4.3: node -> {origin: hops}
    multi_origin_nodes: List[str] = field(default_factory=list)  # FR-4.3: nodes reached from >= 2 origins


@dataclass
class MonteCarloResult(DictCompatible):
    """
    FR-4.4: Result of a Monte Carlo probabilistic propagation simulation.
    Holds per-node infection probabilities aggregated over N independent trials,
    alongside the deterministic BFS PropagationResult for direct comparison.
    """
    n_trials: int
    seed: Optional[int]
    compromised_nodes: List[str]
    scenario_id: str
    infection_probability: Dict[str, float]      # node -> probability [0.0, 1.0]
    infection_std: Dict[str, float]              # node -> std dev of Bernoulli
    infection_count: Dict[str, int]              # node -> raw hit count across trials
    confidence: float                            # mean infection probability across affected nodes
    elapsed_ms: float                            # wall-clock time in milliseconds
    deterministic_result: Optional[object] = None  # PropagationResult for comparison
    partial_propagation_nodes: List[str] = field(default_factory=list)


@dataclass
class GraphSnapshot(DictCompatible):
    """Snapshot envelope of a resolved dependency graph per FR-2.5."""
    snapshot_id: str
    timestamp: str
    schema_version: str = "1.0"
    seeds: List[str] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    max_depth: int = 2
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MitigationRecommendation(DictCompatible):
    """Actionable safeguard recommendation for a package or risk tier."""
    target_node: str
    risk_tier: str
    action_type: str
    description: str
    estimated_impact: str = "HIGH"
    estimated_effort: str = "MEDIUM"
    rank: int = 1


@dataclass
class ConsolidatedFix(DictCompatible):
    """Represents a single high-leverage remediation target (FR-5.2)."""
    rank: int
    package: str
    tier: str
    composite_score: float
    base_cvss: float
    blast_radius_count: int
    newly_covered_count: int
    cumulative_coverage_pct: float
    subsumed_flagged_packages: List[str]
    overlapping_flagged_packages: List[str]
    affected_seeds: List[str]
    explanation: str
    effort_tier: str = "Medium"
    cost_impact_ratio: float = 0.0
    action_type: str = "Pin/upgrade version"


@dataclass
class FixConsolidationReport(DictCompatible):
    """Summary report of consolidated remediation priorities."""
    total_flagged_packages: int
    total_flagged_blast_radius: int
    recommended_fixes: List[ConsolidatedFix]
    top_n_coverage_pct: float
    headline_stat: str
    flagged_packages: List[str]
    ranking_strategy: str = "cost_impact"
    coverage_ranked_fixes: List[ConsolidatedFix] = field(default_factory=list)
    efficiency_ranked_fixes: List[ConsolidatedFix] = field(default_factory=list)

