"""
scoring.py - Calculates composite structural criticality scores,
generates template-based explainability text, and provides risk-tier mitigations.
"""

from typing import Dict, Any, List

from src.models import (
    WeightingConfig,
    CriticalityScore,
    VulnerabilityRecord,
    MitigationRecommendation
)

# Hand-picked CVSS-style base vulnerability scores for representative packages in the graph.
# Reflects historical vulnerability profiles or standard supply-chain risk weights.
MOCKED_CVSS_SEVERITY: Dict[str, float] = {
    "debug": 5.3,              # Widely shared utility, ReDoS / log injection risk
    "follow-redirects": 7.8,   # High: CVE-2024-28849 / credential leak on cross-domain redirect
    "body-parser": 6.5,        # Medium-High: prototype pollution / parsing denial of service
    "qs": 7.2,                 # High: memory exhaustion / depth nesting attack
    "cookie": 5.0,             # Medium: cookie-parser injection / malformed cookie parsing
    "send": 5.3,               # Medium: path traversal risk
    "raw-body": 6.1,           # Medium: length limit bypass
    "express": 2.5,            # Low base severity (mature framework, risk lies in deps)
    "axios": 3.0,              # Low base severity (modern client)
    "cors": 2.0,               # Low base severity
    "morgan": 2.0,             # Low base severity
    "dotenv": 1.5,             # Low base severity
    "ms": 3.7,                 # Low-Medium: regex parsing
    "iconv-lite": 4.5,         # Medium: encoding edge cases
    "http-errors": 4.0,        # Medium: status spoofing
    "mime-types": 2.5,         # Low: lookup table
}

DEFAULT_BENIGN_CVSS: float = 1.0

# Structured mitigation definitions matching FRD MitigationRecommendation model
STRUCTURED_MITIGATIONS: Dict[str, List[Dict[str, str]]] = {
    "CRITICAL": [
        {
            "action_type": "PIN_DIGEST_INTEGRITY",
            "description": "Pin this package to an exact, verified digest hash using package-lock.json / npm shrinkwrap integrity verification.",
            "impact": "HIGH",
            "effort": "LOW"
        },
        {
            "action_type": "RUNTIME_PRIVILEGE_ISOLATION",
            "description": "Isolate network and filesystem privileges of the consuming runtime context to contain blast radius.",
            "impact": "HIGH",
            "effort": "MEDIUM"
        },
        {
            "action_type": "CI_MAINTAINER_GATE",
            "description": "Configure immediate automated build failure in CI/CD upon any upstream maintainer change or transitive version bump.",
            "impact": "HIGH",
            "effort": "LOW"
        }
    ],
    "HIGH": [
        {
            "action_type": "INPUT_SANITIZATION_AUDIT",
            "description": "Audit direct and transitive call-sites across consuming packages to enforce strict input sanitization.",
            "impact": "HIGH",
            "effort": "MEDIUM"
        },
        {
            "action_type": "AUTOMATED_VULN_SCANNING",
            "description": "Enable automated dependency scanning (e.g., npm audit, Socket.dev, Dependabot) with automated patch PR generation.",
            "impact": "MEDIUM",
            "effort": "LOW"
        },
        {
            "action_type": "MODULE_VENDORING_EVAL",
            "description": "Evaluate architectural alternatives or vendoring an audited subset of the module if deep dependencies are unmaintained.",
            "impact": "MEDIUM",
            "effort": "HIGH"
        }
    ],
    "MEDIUM": [
        {
            "action_type": "LOCKFILE_SYNC_REVIEWS",
            "description": "Enforce automated lockfile synchronization and regularly review minor/patch version release notes.",
            "impact": "MEDIUM",
            "effort": "LOW"
        },
        {
            "action_type": "DOWNSTREAM_RESILIENCE_TESTS",
            "description": "Add integration tests verifying that downstream consumers handle unexpected dependency failures gracefully.",
            "impact": "MEDIUM",
            "effort": "MEDIUM"
        },
        {
            "action_type": "NATIVE_API_REPLACEMENT",
            "description": "Assess whether this dependency's functionality can be replaced by native Node.js APIs (e.g. built-in fetch/URL parsing).",
            "impact": "LOW",
            "effort": "HIGH"
        }
    ],
    "LOW": [
        {
            "action_type": "QUARTERLY_DEP_UPDATE",
            "description": "Include in standard quarterly dependency maintenance and scheduled dependency update sprints.",
            "impact": "LOW",
            "effort": "LOW"
        },
        {
            "action_type": "NPM_CI_LOCKFILE_VALIDATION",
            "description": "Ensure the package lockfile is checked into source control and validated via npm ci.",
            "impact": "LOW",
            "effort": "LOW"
        }
    ]
}

# Static mitigation string lookup table
CANNED_MITIGATIONS: Dict[str, List[str]] = {
    tier: [m["description"] for m in mits]
    for tier, mits in STRUCTURED_MITIGATIONS.items()
}


def get_vulnerability_record(package_name: str) -> VulnerabilityRecord:
    """Returns a typed VulnerabilityRecord for the package."""
    pkg = package_name.lower()
    is_curated = pkg in MOCKED_CVSS_SEVERITY
    severity = MOCKED_CVSS_SEVERITY.get(pkg, DEFAULT_BENIGN_CVSS)
    record_id = f"CVE-MOCK-{pkg.upper()}" if is_curated else "CVE-BENIGN-BASE"
    return VulnerabilityRecord(
        id=record_id,
        severity=severity,
        exploit_maturity="POC" if severity >= 7.0 else ("Unproven" if is_curated else "None"),
        patch_availability="Available" if severity >= 5.0 else "N/A",
        is_curated=is_curated
    )


def get_base_severity(package_name: str) -> float:
    """Returns the mocked CVSS-style score (0.0 - 10.0) for a given package."""
    return get_vulnerability_record(package_name).severity


def compute_composite_criticality(
    package_name: str,
    metrics: Dict[str, Any],
    max_in_degree: int,
    max_transitive: int,
    weight_config: Optional[WeightingConfig] = None,
    live_cvss: Optional[float] = None,
    max_betweenness: Optional[float] = None
) -> CriticalityScore:
    """
    Computes a composite criticality score (0 - 100) and returns a typed CriticalityScore entity.
    If live_cvss is provided (from OSV.dev), uses it; otherwise falls back to curated/default baseline.
    If weight_betweenness > 0, incorporates betweenness centrality (fraction of shortest paths).
    """
    if weight_config is None:
        weight_config = WeightingConfig()
    cfg = weight_config.normalize()

    vuln_rec = get_vulnerability_record(package_name)
    if live_cvss is not None:
        cvss = round(float(live_cvss), 1)
        severity_source = "live_osv"
        is_curated = False
    else:
        cvss = vuln_rec.severity
        is_curated = vuln_rec.is_curated
        severity_source = "curated" if is_curated else "default"

    in_degree = metrics.get("in_degree", 0)
    transitive = metrics.get("transitive_dependents_count", 0)
    betweenness = metrics.get("betweenness_centrality", 0.0)

    norm_cvss = (cvss / 10.0) * 100.0
    norm_in_deg = (in_degree / max(max_in_degree, 1)) * 100.0
    norm_trans = (transitive / max(max_transitive, 1)) * 100.0
    norm_between = (betweenness / max_betweenness * 100.0) if (max_betweenness and max_betweenness > 0) else (betweenness * 100.0)

    vuln_subscore = cfg.weight_cvss * norm_cvss
    struct_subscore = (
        (cfg.weight_transitive * norm_trans)
        + (cfg.weight_indegree * norm_in_deg)
        + (cfg.weight_betweenness * norm_between)
    )
    raw_score = vuln_subscore + struct_subscore
    score = min(100.0, max(0.0, round(raw_score, 1)))

    if score >= 70.0:
        tier = "CRITICAL"
        tier_color = "#e63946"  # Coral red
    elif score >= 45.0:
        tier = "HIGH"
        tier_color = "#f4a261"  # Amber orange
    elif score >= 25.0:
        tier = "MEDIUM"
        tier_color = "#b388eb"  # Lavender accent
    else:
        tier = "LOW"
        tier_color = "#005f73"  # Deep peacock green

    # FR-3.5: Hidden Critical flag: low/modest CVSS (<= 5.5) but HIGH or CRITICAL composite score
    is_hidden_critical = bool(cvss <= 5.5 and tier in ["CRITICAL", "HIGH"])

    return CriticalityScore(
        node_id=package_name,
        composite_score=score,
        structural_subscore=round(struct_subscore, 1),
        vulnerability_subscore=round(vuln_subscore, 1),
        weighting_config=cfg,
        tier=tier,
        tier_color=tier_color,
        cvss=cvss,
        is_curated_cve=is_curated,
        is_hidden_critical=is_hidden_critical,
        in_degree=in_degree,
        transitive_dependents=transitive,
        norm_cvss=round(norm_cvss, 1),
        norm_in_deg=round(norm_in_deg, 1),
        norm_trans=round(norm_trans, 1),
        severity_source=severity_source,
        betweenness_centrality=round(betweenness, 6),
        norm_between=round(norm_between, 1),
        norm_betweenness=round(norm_between, 1)
    )


def generate_explanation(package_name: str, score_data: Dict[str, Any], metrics: Dict[str, Any]) -> str:
    """
    Template-based (f-string) plain-language explanation of why a package
    received its criticality score and risk tier.
    """
    tier = score_data["tier"]
    score = score_data["score"]
    cvss = score_data["cvss"]
    in_deg = score_data["in_degree"]
    trans = score_data["transitive_dependents"]
    affected_seeds = metrics.get("affected_seeds", [])
    seed_count = len(affected_seeds)
    seed_names = ", ".join(f"`{s}`" for s in affected_seeds[:3])
    if seed_count > 3:
        seed_names += f" and {seed_count - 3} more"

    if in_deg == 0 and trans == 0:
        return (
            f"**{package_name}** is ranked as **{tier} RISK** ({score}/100). "
            f"It is a leaf consumer or root application with no upstream internal dependents in this graph. "
            f"With an isolated base severity of CVSS {cvss}/10, a compromise here does not propagate to other packages."
        )

    if trans >= 5 and cvss <= 5.5:
        return (
            f"**{package_name}** is flagged as **{tier} RISK** ({score}/100) due to **structural amplification**: "
            f"while its individual baseline vulnerability score is modest (CVSS {cvss}/10), it acts as a foundational dependency. "
            f"A breach here ripples into **{trans} transitive packages** ({in_deg} direct dependents), directly exposing "
            f"**{seed_count} top-level application seeds** ({seed_names})."
        )
    elif cvss >= 7.0 and trans >= 4:
        return (
            f"**{package_name}** is flagged as **{tier} RISK** ({score}/100) due to **severe compound exposure**: "
            f"it possesses a high intrinsic vulnerability score (CVSS {cvss}/10) coupled with a critical blast radius of "
            f"**{trans} transitive dependents**. Compromising this node immediately threatens **{seed_count} application seeds** ({seed_names})."
        )
    elif cvss >= 6.0 and trans < 4:
        return (
            f"**{package_name}** is rated as **{tier} RISK** ({score}/100): "
            f"despite an elevated vulnerability score (CVSS {cvss}/10), its systemic risk is moderated by a contained "
            f"blast radius of **{trans} downstream dependents** ({in_deg} direct)."
        )
    else:
        return (
            f"**{package_name}** is classified as **{tier} RISK** ({score}/100). "
            f"It exhibits a balanced risk profile with a baseline CVSS of {cvss}/10, affecting **{trans} transitive packages** "
            f"across {seed_count} top-level seed applications ({seed_names})."
        )


def get_mitigations_for_tier(tier: str) -> List[str]:
    """Returns canned static recommendations for the given risk tier."""
    return CANNED_MITIGATIONS.get(tier.upper(), CANNED_MITIGATIONS["LOW"])
