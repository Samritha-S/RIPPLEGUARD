"""
visualizer.py - Interactive Pyvis force-directed graph generator
styled with Peacock Green & Lavender theme for RippleGuard.
"""

from typing import Dict, Any, Optional, Set, List
import networkx as nx
from pyvis.network import Network


# Theme Palette
COLOR_PEACOCK_DARK = "#092429"
COLOR_PEACOCK_PRIMARY = "#005f73"
COLOR_PEACOCK_LIGHT = "#0a9396"
COLOR_PEACOCK_MUTED = "#1d3e42"
COLOR_LAVENDER_ACCENT = "#c8b6ff"
COLOR_LAVENDER_VIBRANT = "#b388eb"
COLOR_LAVENDER_LIGHT = "#e7c6ff"
COLOR_COMPROMISED_ROOT = "#ff4d6d"
COLOR_MULTI_ORIGIN = "#ffb703"
COLOR_MULTI_ORIGIN_BORDER = "#ffffff"
COLOR_BACKGROUND = "#0a1315"
COLOR_TEXT = "#e0e7e9"

# Risk tier colors
TIER_COLORS = {
    "CRITICAL": "#e63946",
    "HIGH": "#f4a261",
    "MEDIUM": COLOR_LAVENDER_VIBRANT,
    "LOW": COLOR_PEACOCK_PRIMARY
}


def create_pyvis_graph(
    G: nx.DiGraph,
    metrics: Dict[str, Dict[str, Any]],
    scores: Dict[str, Dict[str, Any]],
    selected_node: Optional[str] = None,
    simulation_result: Optional[Dict[str, Any]] = None,
    mc_probabilities: Optional[Dict[str, float]] = None,
    height: str = "620px",
    cdn_resources: str = "in_line"
) -> str:
    """
    Builds and returns an interactive Pyvis HTML string for Streamlit embedding.
    Uses in-line vis.js resources by default for 100% offline capability.

    If simulation_result is provided, highlights:
    - Root compromised nodes in glowing red/magenta
    - Multi-origin overlapping blast radius nodes in golden amber (FR-4.3)
    - Downstream affected packages in vibrant lavender

    If mc_probabilities is provided (FR-4.4 Monte Carlo mode), affected nodes
    are shaded with opacity proportional to their infection probability, and the
    probability is shown in the node tooltip.
    - Propagation attack paths in luminous lavender edges
    - Dimmed unaffected nodes & edges
    """
    net = Network(
        height=height,
        width="100%",
        directed=True,
        bgcolor=COLOR_BACKGROUND,
        font_color=COLOR_TEXT,
        cdn_resources=cdn_resources
    )

    is_simulating = simulation_result is not None and bool(
        simulation_result.get("compromised_node") or simulation_result.get("compromised_nodes")
    )
    affected_nodes: Set[str] = set()
    propagation_edges: Set[tuple] = set()
    compromised_roots: Set[str] = set()
    multi_origin_nodes: Set[str] = set()
    origin_reachability: Dict[str, Dict[str, int]] = {}

    if is_simulating:
        raw_roots = simulation_result.get("compromised_nodes") or []
        if not raw_roots and simulation_result.get("compromised_node"):
            c_node = simulation_result["compromised_node"]
            raw_roots = [n.strip() for n in c_node.split(",")] if isinstance(c_node, str) else list(c_node)
        compromised_roots = set(raw_roots)
        affected_nodes = set(simulation_result.get("affected_nodes", []))
        multi_origin_nodes = set(simulation_result.get("multi_origin_nodes", []))
        origin_reachability = simulation_result.get("origin_reachability", {})
        # Note: propagation_edges are (from_node, to_node) in attack order (compromised -> dependent)
        for u, v in simulation_result.get("propagation_edges", []):
            # In G, the dependency edge is v -> u ("v depends on u")
            # We will highlight edge v -> u in G
            propagation_edges.add((v, u))

    # Add Nodes
    for node_id in G.nodes():
        node_meta = G.nodes[node_id]
        m = metrics.get(node_id, {})
        sc = scores.get(node_id, {"score": 10.0, "tier": "LOW", "cvss": 1.0})

        is_seed = node_meta.get("is_seed", False)
        in_deg = m.get("in_degree", 0)
        trans_count = m.get("transitive_dependents_count", 0)
        cvss = sc.get("cvss", 1.0)
        score = sc.get("score", 10.0)
        tier = sc.get("tier", "LOW")

        # Base sizing: proportional to criticality score & in-degree
        base_size = max(14, int(14 + (score / 100.0) * 22))

        # Tooltip content
        lic = node_meta.get("license")
        pub = node_meta.get("publish_date")
        lic_html = f"<b>License:</b> {lic}<br/>" if lic else ""
        pub_html = f"<b>Published:</b> {str(pub)[:10]}<br/>" if pub else ""

        sim_status_html = ""
        mc_prob_html = ""
        if is_simulating:
            if node_id in compromised_roots:
                sim_status_html = "<div style='margin-top:6px; padding:3px 6px; background:rgba(255,77,109,0.25); border:1px solid #ff4d6d; border-radius:4px; font-size:11px; color:#ff85a1;'><b>🚨 Compromised Origin</b></div>"
            elif node_id in multi_origin_nodes:
                reaches = origin_reachability.get(node_id, {})
                reach_str = " & ".join([f"{orig} ({d}h)" for orig, d in reaches.items()])
                sim_status_html = f"<div style='margin-top:6px; padding:3px 6px; background:rgba(255,183,3,0.2); border:1px solid #ffb703; border-radius:4px; font-size:11px; color:#ffd166;'><b>⚡ Multi-Origin Blast Overlap</b><br/>Via: {reach_str}</div>"
            elif node_id in affected_nodes:
                reaches = origin_reachability.get(node_id, {})
                min_h = min(reaches.values()) if reaches else 1
                sim_status_html = f"<div style='margin-top:6px; padding:3px 6px; background:rgba(179,136,235,0.2); border:1px solid #b388eb; border-radius:4px; font-size:11px; color:#e7c6ff;'><b>⚠️ Downstream Blast</b> ({min_h} hop)</div>"
            # FR-4.4: Monte Carlo probability in tooltip
            if mc_probabilities and node_id in mc_probabilities:
                mp = mc_probabilities[node_id]
                mc_prob_html = (
                    f"<div style='margin-top:4px; padding:3px 6px; background:rgba(100,100,200,0.15); "
                    f"border:1px solid #888; border-radius:4px; font-size:11px; color:#c8b6ff;'>"
                    f"<b>🎲 MC Infection Probability: {mp:.1%}</b>"
                    f"<br/><span style='color:#888; font-size:10px;'>Heuristic estimate — version pin constraints</span>"
                    f"</div>"
                )

        title_html = (
            f"<div style='font-family:sans-serif; padding:6px; min-width:180px;'>"
            f"<b style='font-size:14px; color:{COLOR_LAVENDER_ACCENT};'>{node_id}</b>"
            f"<span style='font-size:11px; color:#aaa;'> v{node_meta.get('version', '')}</span><br/>"
            f"<hr style='margin:4px 0; border:0; border-top:1px solid #444;'/>"
            f"<b>Risk Tier:</b> <span style='color:{TIER_COLORS.get(tier, '#fff')};'>{tier}</span> ({score}/100)<br/>"
            f"<b>Base CVSS:</b> {cvss}/10<br/>"
            f"<b>Direct Dependents (In-Deg):</b> {in_deg}<br/>"
            f"<b>Transitive Blast Radius:</b> {trans_count} packages<br/>"
            f"{lic_html}"
            f"{pub_html}"
            f"<b>Role:</b> {'🌟 Top-level Seed' if is_seed else 'Transitive Dependency'}"
            f"{sim_status_html}"
            f"{mc_prob_html}"
            f"</div>"
        )

        # Visual styling depending on state
        if is_simulating:
            if node_id in compromised_roots:
                node_color = {
                    "background": COLOR_COMPROMISED_ROOT,
                    "border": "#ffffff",
                    "highlight": {"background": "#ff1744", "border": "#ffffff"}
                }
                size = base_size + 14
                shape = "star" if is_seed else "dot"
                border_width = 3
                label = f"🚨 {node_id}"
            elif node_id in multi_origin_nodes:
                # FR-4.3: Distinct Golden Amber styling for multi-origin overlapping blast radius
                node_color = {
                    "background": COLOR_MULTI_ORIGIN,
                    "border": COLOR_MULTI_ORIGIN_BORDER,
                    "highlight": {"background": "#ffe066", "border": "#ffffff"}
                }
                size = base_size + 8
                shape = "triangle" if not is_seed else "diamond"
                border_width = 3
                label = f"⚡ {node_id}"
            elif node_id in affected_nodes:
                # FR-4.4: If MC probabilities provided, blend color by infection probability
                if mc_probabilities and node_id in mc_probabilities:
                    mp = mc_probabilities[node_id]
                    # Scale from dim (p=0) to full lavender (p=1) via RGB interpolation
                    # Full: rgb(179, 136, 235)  Dim: rgb(30, 40, 55)
                    r = int(30 + (179 - 30) * mp)
                    g = int(40 + (136 - 40) * mp)
                    b = int(55 + (235 - 55) * mp)
                    bg_color = f"rgb({r},{g},{b})"
                    node_color = {
                        "background": bg_color,
                        "border": COLOR_LAVENDER_LIGHT,
                        "highlight": {"background": COLOR_LAVENDER_LIGHT, "border": "#ffffff"}
                    }
                    label = f"🎲 {int(mp * 100)}% {node_id}"
                else:
                    node_color = {
                        "background": COLOR_LAVENDER_VIBRANT,
                        "border": COLOR_LAVENDER_LIGHT,
                        "highlight": {"background": COLOR_LAVENDER_LIGHT, "border": "#ffffff"}
                    }
                    label = f"⚠️ {node_id}"
                size = base_size + 6
                shape = "diamond" if is_seed else "dot"
                border_width = 2
            else:
                # Dimmed unaffected node
                node_color = {
                    "background": COLOR_PEACOCK_MUTED,
                    "border": "#13272a",
                    "highlight": {"background": COLOR_PEACOCK_PRIMARY, "border": COLOR_LAVENDER_ACCENT}
                }
                size = 9
                shape = "dot"
                border_width = 1
                label = node_id
        else:
            # Standard View (Tier colors)
            tier_col = TIER_COLORS.get(tier, COLOR_PEACOCK_PRIMARY)
            border_col = COLOR_LAVENDER_ACCENT if node_id == selected_node else (COLOR_PEACOCK_LIGHT if is_seed else tier_col)
            border_width = 4 if node_id == selected_node else (2 if is_seed else 1)

            node_color = {
                "background": tier_col,
                "border": border_col,
                "highlight": {"background": COLOR_LAVENDER_VIBRANT, "border": "#ffffff"}
            }
            size = base_size + (4 if node_id == selected_node else 0)
            shape = "diamond" if is_seed else "dot"
            label = f"★ {node_id}" if is_seed else node_id

        net.add_node(
            node_id,
            label=label,
            title=title_html,
            color=node_color,
            size=size,
            shape=shape,
            borderWidth=border_width,
            font={"color": COLOR_TEXT, "size": 12, "face": "Segoe UI, sans-serif"}
        )

    # Add Edges (source -> target means 'source depends on target')
    for src, tgt in G.edges():
        is_prop_edge = (src, tgt) in propagation_edges

        if is_simulating:
            if is_prop_edge:
                edge_color = {
                    "color": COLOR_LAVENDER_ACCENT,
                    "highlight": COLOR_LAVENDER_LIGHT,
                    "opacity": 1.0
                }
                width = 3.5
            elif src in affected_nodes and tgt in affected_nodes:
                edge_color = {
                    "color": COLOR_LAVENDER_VIBRANT,
                    "highlight": COLOR_LAVENDER_LIGHT,
                    "opacity": 0.7
                }
                width = 2.0
            else:
                edge_color = {
                    "color": "#182c30",
                    "highlight": COLOR_PEACOCK_LIGHT,
                    "opacity": 0.15
                }
                width = 0.8
        else:
            edge_color = {
                "color": "#1f484f",
                "highlight": COLOR_LAVENDER_ACCENT,
                "opacity": 0.5
            }
            width = 1.2

        net.add_edge(
            src,
            tgt,
            color=edge_color,
            width=width,
            arrows={"to": {"enabled": True, "scaleFactor": 0.55}}
        )

    # Configure physics for smooth force-directed stabilization
    options_json = """
    var options = {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -3800,
          "centralGravity": 0.25,
          "springLength": 90,
          "springConstant": 0.045,
          "damping": 0.12,
          "avoidOverlap": 0.25
        },
        "maxVelocity": 28,
        "minVelocity": 0.5,
        "solver": "barnesHut",
        "stabilization": {
          "enabled": true,
          "iterations": 120
        }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 150,
        "navigationButtons": true,
        "keyboard": false,
        "zoomView": true
      }
    }
    """
    net.set_options(options_json)

    html_content = net.generate_html()
    return html_content
