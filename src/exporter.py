"""
exporter.py - Generates standalone Markdown scenario audit reports for RippleGuard.
Summarizes package criticality, structural reach, compromise simulations,
and Fix Consolidation recommendations with full disclosures.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone


def generate_scenario_report(
    package_name: str,
    score_data: Dict[str, Any],
    metrics: Dict[str, Any],
    explanation: str,
    ecosystem: str = "npm",
    active_source_label: str = "Demo dataset (5 npm seeds)",
    snapshot_id: Optional[str] = None,
    simulation_result: Optional[Any] = None,
    fix_report: Optional[Any] = None,
    mc_result: Optional[Any] = None
) -> str:
    """
    Generate an explainable Markdown audit report for the currently inspected package scenario.
    Provides complete transparency regarding data origin, severity curation, and graph metrics.
    """
    score = score_data.get("score", score_data.get("composite_score", 0.0))
    tier = score_data.get("tier", "LOW")
    cvss = score_data.get("cvss", 1.0)
    is_curated = score_data.get("is_curated_cve", False)
    is_hidden_critical = score_data.get("is_hidden_critical", False)
    severity_src = score_data.get("severity_source", "curated" if is_curated else "default")
    if severity_src == "live_osv":
        cvss_label = "Live OSV.dev Advisory"
    elif is_curated:
        cvss_label = "Curated CVE Profile"
    else:
        cvss_label = "Default Benign Baseline"

    # FR-5.5: Confidence Proxy Label
    conf_label = (
        "High confidence (curated/live data)"
        if severity_src in ["curated", "live_osv"]
        else "Estimated (default baseline)"
    )

    in_deg = metrics.get("in_degree", 0)
    trans_count = metrics.get("transitive_dependents_count", 0)
    version = metrics.get("version", "unknown")
    license_str = metrics.get("license") or "Not specified"
    publish_date = str(metrics.get("publish_date"))[:10] if metrics.get("publish_date") else "Unknown"
    affected_seeds = metrics.get("affected_seeds", [])
    seed_str = ", ".join(f"`{s}`" for s in affected_seeds) if affected_seeds else "None"

    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    snap_str = snapshot_id or "rg-snap-live"

    lines = [
        f"# 🛡️ RippleGuard Scenario Audit Report: `{package_name}`",
        "",
        f"> **Generated:** {timestamp_str}  ",
        f"> **UN SDG 9 Alignment:** Industry, Innovation & Infrastructure • Software Supply Chain Resilience",
        "",
        "---",
        "",
        "## 1. Transparency & Data Source Disclosures",
        "",
        f"- **Ecosystem:** `{ecosystem}`",
        f"- **Active Graph Source:** `{active_source_label}`",
        f"- **Graph Snapshot ID:** `{snap_str}`",
        f"- **Vulnerability Severity Status:** **{cvss_label}** ({cvss}/10.0 CVSS)",
        "",
        "> **⚠️ Supply Chain Severity Caveat:**  ",
        "> In this deployment, vulnerability severity data is derived from curated representative supply-chain profiles for representative packages or a standard default baseline (1.0/10.0) to ensure reliable offline demonstration. All topological metrics (in-degree, transitive blast radius, shortest propagation attack paths, and Fix Consolidation greedy set-cover ranking) are **100% computed directly from the resolved dependency graph topology**.",
        "",
        "---",
        "",
        "## 2. Package Profile & Structural Metrics",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| **Package Name** | `{package_name}` |",
        f"| **Version** | `v{version}` |",
        f"| **License** | {license_str} |",
        f"| **Publish Date** | {publish_date} |",
        f"| **Composite Criticality Score** | **{score:.1f} / 100** |",
        f"| **Assigned Risk Tier** | **{tier} RISK** |",
        f"| **Base Severity (CVSS)** | **{cvss:.1f} / 10.0** ({cvss_label}) |",
        f"| **Direct Dependents (In-Degree)** | **{in_deg}** packages |",
        f"| **Transitive Blast Radius** | **{trans_count}** downstream packages |",
        f"| **Exposed Application Seeds** | {seed_str} ({len(affected_seeds)} total) |",
        f"| **Hidden Critical Anomaly (FR-3.5)** | **{'⚠️ Yes (Amplified by Topological Reach)' if is_hidden_critical else 'No'}** |",
        f"| **Confidence Assessment (FR-5.5)** | **{conf_label}** |",
        "",
        "---",
        "",
        "## 3. Explainable Risk Assessment",
        "",
        f"{explanation}",
        "",
        "---",
    ]

    # Section 4: Compromise Simulation
    lines.append("## 4. Downstream Compromise Simulation")
    lines.append("")
    # Check if a simulation was actively run for this package (single or multi-origin)
    sim_pkg = None
    origins = []
    if simulation_result:
        sim_pkg = simulation_result.get("compromised_node") if isinstance(simulation_result, dict) else getattr(simulation_result, "compromised_node", None)
        origins = simulation_result.get("compromised_nodes", [sim_pkg]) if isinstance(simulation_result, dict) else getattr(simulation_result, "compromised_nodes", [sim_pkg])

    is_active_for_pkg = sim_pkg and (sim_pkg == package_name or package_name in origins)

    if is_active_for_pkg:
        aff_count = simulation_result.get("affected_count") if isinstance(simulation_result, dict) else getattr(simulation_result, "affected_count", 0)
        aff_nodes = simulation_result.get("affected_nodes") if isinstance(simulation_result, dict) else getattr(simulation_result, "affected_nodes", [])
        aff_seeds = simulation_result.get("affected_seeds") if isinstance(simulation_result, dict) else getattr(simulation_result, "affected_seeds", [])
        max_hops = simulation_result.get("max_hops") if isinstance(simulation_result, dict) else getattr(simulation_result, "max_hops", 0)
        paths = simulation_result.get("propagation_paths") if isinstance(simulation_result, dict) else getattr(simulation_result, "propagation_paths", {})
        levels = simulation_result.get("levels") if isinstance(simulation_result, dict) else getattr(simulation_result, "levels", {})
        multi_origins = simulation_result.get("multi_origin_nodes", []) if isinstance(simulation_result, dict) else getattr(simulation_result, "multi_origin_nodes", [])

        if trans_count == 0 and len(origins) <= 1:
            lines.append(f"**Containment Status:** 🛡️ **Zero-Downstream Root Application**")
            lines.append(f"- Compromising `{package_name}` is **completely contained**: it has no upstream dependents in this graph (0 transitive hops).")
        else:
            sim_title = "🚨 **Active Compromise Simulated**"
            if len(origins) > 1:
                sim_title = f"🚨 **Multi-Origin Compromise Active ({len(origins)} Origins: `{', '.join(origins)}`)**"
            lines.append(f"**Simulation Status:** {sim_title}")

            if mc_result:
                n_tr = getattr(mc_result, "n_trials", 1000)
                ms = getattr(mc_result, "elapsed_ms", 0.0)
                conf = getattr(mc_result, "confidence", 0.0)
                lines.append(f"- **Simulation Mode:** 🎲 **Monte Carlo Probabilistic Propagation** ({n_tr:,} trials in {ms:.1f} ms)")
                lines.append(f"- **Mean Infection Confidence:** **{conf:.1%}** across reached components")
            else:
                lines.append(f"- **Simulation Mode:** 💥 **Deterministic BFS (Worst-Case)**")

            lines.append(f"- **Total Affected Packages:** **{aff_count}** downstream components")
            lines.append(f"- **Maximum Propagation Distance:** **{max_hops}** hop(s)")
            lines.append(f"- **Threatened Application Seeds ({len(aff_seeds)}):** " + ", ".join(f"`{s}`" for s in aff_seeds))

            if multi_origins:
                lines.append(f"- **Multi-Origin Blast Overlap ({len(multi_origins)} packages):** " + ", ".join(f"`{m}`" for m in multi_origins))

            if mc_result:
                partials = getattr(mc_result, "partial_propagation_nodes", [])
                if partials:
                    lines.append(f"- **Partial-Propagation Nodes (<95% likelihood):** " + ", ".join(f"`{n}`" for n in partials))
                lines.append("")
                lines.append("### Monte Carlo Per-Node Probabilities:")
                lines.append("| Package | Likelihood | Std Dev (±) | Assessment |")
                lines.append("| :--- | :--- | :--- | :--- |")
                mc_p = getattr(mc_result, "infection_probability", {})
                mc_std = getattr(mc_result, "infection_std", {})
                for p_n, p_v in sorted(mc_p.items(), key=lambda x: -x[1])[:8]:
                    tag = "Origin" if p_n in origins else ("Partial" if p_n in partials else "Certain")
                    lines.append(f"| `{p_n}` | **{p_v:.1%}** | ±{mc_std.get(p_n, 0.0):.4f} | {tag} |")

            lines.append("")
            lines.append("### Shortest Attack Propagation Paths to Application Seeds:")
            for s in aff_seeds:
                p_list = paths.get(s, [s])
                path_str = " ➔ ".join(f"`{node}`" for node in p_list)
                lines.append(f"- **Target `{s}`:** {path_str}")
            lines.append("")
            lines.append("### Infection Stages by Hop Distance:")
            for hop, pkgs in sorted(levels.items()):
                hop_label = "Compromised Origin" if hop == 0 else f"Hop {hop} Downstream"
                sample_pkgs = ", ".join(f"`{p}`" for p in pkgs[:8])
                if len(pkgs) > 8:
                    sample_pkgs += f" and {len(pkgs) - 8} more"
                lines.append(f"- **{hop_label} ({len(pkgs)}):** {sample_pkgs}")
    else:
        lines.append("*Compromise propagation simulation was not executed for this package in the active UI session.*")
        lines.append(f"- Transitive blast radius indicates that compromising `{package_name}` would reach up to **{trans_count} downstream packages**.")
        if affected_seeds:
            lines.append(f"- Top-level application seeds in line of fire: " + ", ".join(f"`{s}`" for s in affected_seeds) + ".")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 5: Fix Consolidation ("Fix This First") - FR-5.2 Dual Rankings
    lines.append("## 5. Consolidated Remediation Priorities (\"Fix This First\")")
    lines.append("")
    if fix_report:
        headline = fix_report.get("headline_stat") if isinstance(fix_report, dict) else getattr(fix_report, "headline_stat", "")
        fixes = fix_report.get("recommended_fixes", []) if isinstance(fix_report, dict) else getattr(fix_report, "recommended_fixes", [])
        eff_fixes = fix_report.get("efficiency_ranked_fixes", []) if isinstance(fix_report, dict) else getattr(fix_report, "efficiency_ranked_fixes", [])
        cov_fixes = fix_report.get("coverage_ranked_fixes", []) if isinstance(fix_report, dict) else getattr(fix_report, "coverage_ranked_fixes", [])

        if headline:
            lines.append(f"> **Triage Strategy:** {headline}")
            lines.append("")

        lines.append("> **⚠️ Mitigation Effort Disclosure (FR-5.2):** Effort tiers (Low, Low-Medium, Medium, High, Very High) are heuristic estimates based on action classification and pin status, not measured engineering labor data.")
        lines.append("")

        # Primary Active Ranking
        if fixes:
            lines.append("### Recommended Remediation Sequence (Active Strategy):")
            for fix in fixes[:4]:
                rank = fix.get("rank") if isinstance(fix, dict) else getattr(fix, "rank", 1)
                pkg = fix.get("package") if isinstance(fix, dict) else getattr(fix, "package", "")
                f_tier = fix.get("tier") if isinstance(fix, dict) else getattr(fix, "tier", "HIGH")
                f_score = fix.get("composite_score") if isinstance(fix, dict) else getattr(fix, "composite_score", 0.0)
                cum_pct = fix.get("cumulative_coverage_pct") if isinstance(fix, dict) else getattr(fix, "cumulative_coverage_pct", 0.0)
                blast = fix.get("blast_radius_count") if isinstance(fix, dict) else getattr(fix, "blast_radius_count", 0)
                subsumed = fix.get("subsumed_flagged_packages", []) if isinstance(fix, dict) else getattr(fix, "subsumed_flagged_packages", [])
                exp = fix.get("explanation") if isinstance(fix, dict) else getattr(fix, "explanation", "")

                sub_note = f" (subsumes alert for `{', '.join(subsumed)}`)" if subsumed else ""
                eff = fix.get("effort_tier") if isinstance(fix, dict) else getattr(fix, "effort_tier", None)
                ratio = fix.get("cost_impact_ratio") if isinstance(fix, dict) else getattr(fix, "cost_impact_ratio", None)
                act = fix.get("action_type") if isinstance(fix, dict) else getattr(fix, "action_type", None)

                lines.append(f"1. **#{rank} Priority Fix: `{pkg}`** [{f_tier} • {f_score:.1f}/100]{sub_note}")
                lines.append(f"   - **Cumulative Risk Covered:** **{cum_pct:.1f}%** (Blast Radius: {blast} packages)")
                if eff:
                    roi_str = f" • Cost/Impact ROI: {ratio:.1f}" if ratio is not None else ""
                    act_str = f" • Action: {act}" if act else ""
                    lines.append(f"   - **Effort Tier:** **{eff} Effort**{roi_str}{act_str}")
                lines.append(f"   - **Rationale:** {exp}")
            lines.append("")

        # Dual Rankings Comparison (FR-5.2)
        if eff_fixes and cov_fixes:
            lines.append("### Two-Dimensional Ranking Comparison (FR-5.2):")
            lines.append("")
            lines.append("| Rank | Efficiency Order (Coverage ÷ Effort) | Coverage Order (Pure Blast Reach) |")
            lines.append("| :--- | :--- | :--- |")
            max_r = max(len(eff_fixes), len(cov_fixes))
            for i in range(min(max_r, 4)):
                e_str = f"`{eff_fixes[i].package}` ({eff_fixes[i].effort_tier} effort, ROI {eff_fixes[i].cost_impact_ratio:.1f})" if i < len(eff_fixes) else "-"
                c_str = f"`{cov_fixes[i].package}` ({cov_fixes[i].cumulative_coverage_pct:.1f}% cum. coverage)" if i < len(cov_fixes) else "-"
                lines.append(f"| **#{i+1}** | {e_str} | {c_str} |")
            lines.append("")
        elif not fixes:
            lines.append("*No packages currently exceed the high/critical alert threshold under active weights.*")
    else:
        lines.append("*Fix consolidation analysis not loaded for this scenario.*")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Report generated by RippleGuard Supply Chain Risk Intelligence System.*")

    return "\n".join(lines)
