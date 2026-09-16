"""
manifest_parser.py - Ingests software dependency manifests and CycloneDX SBOMs
to construct RippleGuard dependency graphs without live network crawling.
"""

import json
import logging
from typing import Dict, Any, List, Set, Optional, Tuple, Union
from datetime import datetime, timezone
import hashlib

logger = logging.getLogger("RippleGuard.ManifestParser")


class ManifestParseError(Exception):
    """Raised when an uploaded manifest or SBOM is malformed or unsupported."""
    pass


def parse_package_lock(data: Dict[str, Any], source_name: str = "package-lock.json") -> Dict[str, Any]:
    """
    Parses an npm package-lock.json file (supporting lockfileVersion 1, 2, and 3).
    Extracts package nodes and dependency edges, outputting the standard
    RippleGuard graph structure.
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    edges_set: Set[Tuple[str, str, str]] = set()
    seed_names: Set[str] = set()

    # Determine lockfile version
    lockfile_version = data.get("lockfileVersion", 1)

    # Strategy for lockfileVersion 2 & 3: uses 'packages' object
    if "packages" in data and isinstance(data["packages"], dict):
        packages = data["packages"]
        root_pkg = packages.get("", {})
        root_deps = root_pkg.get("dependencies", {})
        root_dev_deps = root_pkg.get("devDependencies", {})

        # Seeds are the root project's declared direct dependencies
        for dep in root_deps.keys():
            seed_names.add(dep.strip().lower())
        for dep in root_dev_deps.keys():
            seed_names.add(dep.strip().lower())

        for pkg_path, pkg_info in packages.items():
            if not isinstance(pkg_info, dict):
                continue

            # Extract clean package name from 'node_modules/foo/node_modules/bar' -> 'bar'
            if pkg_path == "":
                # Root application itself
                root_name = data.get("name") or "root-application"
                pkg_name = root_name.strip().lower()
                version = data.get("version", "1.0.0")
                is_root = True
            else:
                parts = pkg_path.split("node_modules/")
                pkg_name = parts[-1].strip().lower()
                version = pkg_info.get("version", "unknown")
                is_root = False

            if not pkg_name:
                continue

            # License handling
            raw_lic = pkg_info.get("license")
            if isinstance(raw_lic, dict):
                lic_str = raw_lic.get("type")
            elif isinstance(raw_lic, str):
                lic_str = raw_lic
            else:
                lic_str = None

            is_seed = (pkg_name in seed_names) or is_root

            if pkg_name not in nodes:
                nodes[pkg_name] = {
                    "id": pkg_name,
                    "name": pkg_name,
                    "ecosystem": "npm",
                    "version": version,
                    "publish_date": None,
                    "maintainers": None,
                    "downloads": None,
                    "known_cves": [],
                    "license": lic_str,
                    "description": pkg_info.get("description") or f"Ingested from {source_name}",
                    "depth": 0 if is_seed else 1,
                    "is_seed": is_seed
                }
            else:
                if is_seed:
                    nodes[pkg_name]["is_seed"] = True
                    nodes[pkg_name]["depth"] = 0
                if nodes[pkg_name]["version"] == "unknown" and version != "unknown":
                    nodes[pkg_name]["version"] = version

            # Dependencies
            deps = pkg_info.get("dependencies", {})
            if isinstance(deps, dict):
                for dep_name, dep_spec in deps.items():
                    target_name = dep_name.strip().lower()
                    edges_set.add((pkg_name, target_name, str(dep_spec)))

    # Strategy for lockfileVersion 1 (or fallback if packages missing): uses nested 'dependencies'
    elif "dependencies" in data and isinstance(data["dependencies"], dict):
        def walk_v1_dependencies(parent_name: str, deps_dict: Dict[str, Any], current_depth: int):
            for dep_name, dep_info in deps_dict.items():
                if not isinstance(dep_info, dict):
                    continue
                clean_name = dep_name.strip().lower()
                version = dep_info.get("version", "unknown")
                is_seed = (current_depth == 0)

                if clean_name not in nodes:
                    nodes[clean_name] = {
                        "id": clean_name,
                        "name": clean_name,
                        "ecosystem": "npm",
                        "version": version,
                        "publish_date": None,
                        "maintainers": None,
                        "downloads": None,
                        "known_cves": [],
                        "license": None,
                        "description": f"Ingested from {source_name}",
                        "depth": current_depth,
                        "is_seed": is_seed
                    }
                else:
                    if is_seed:
                        nodes[clean_name]["is_seed"] = True
                        nodes[clean_name]["depth"] = 0

                if parent_name:
                    edges_set.add((parent_name, clean_name, version))

                # Recurse for nested dependencies
                nested = dep_info.get("dependencies", {})
                if isinstance(nested, dict) and nested:
                    walk_v1_dependencies(clean_name, nested, current_depth + 1)

        root_name = data.get("name") or "root-application"
        root_clean = root_name.strip().lower()
        nodes[root_clean] = {
            "id": root_clean,
            "name": root_clean,
            "ecosystem": "npm",
            "version": data.get("version", "1.0.0"),
            "publish_date": None,
            "maintainers": None,
            "downloads": None,
            "known_cves": [],
            "license": None,
            "description": f"Root project from {source_name}",
            "depth": 0,
            "is_seed": True
        }
        walk_v1_dependencies(root_clean, data["dependencies"], 0)
    else:
        raise ManifestParseError(
            f"Invalid package-lock.json in '{source_name}': missing both 'packages' and 'dependencies' blocks."
        )

    if not nodes:
        raise ManifestParseError(f"No valid packages found in '{source_name}'.")

    # Compute accurate BFS depth from seed nodes
    import networkx as nx
    G = nx.DiGraph()
    for n in nodes.keys():
        G.add_node(n)
    for src, tgt, spec in edges_set:
        G.add_edge(src, tgt)

    seeds = [n for n, d in nodes.items() if d.get("is_seed", False)]
    if not seeds:
        # Fallback: in-degree 0 nodes as seeds
        seeds = [n for n in G.nodes() if G.in_degree(n) == 0]
        for s in seeds:
            nodes[s]["is_seed"] = True
            nodes[s]["depth"] = 0

    # BFS from seeds to compute correct depths
    for seed in seeds:
        for target, length in nx.single_source_shortest_path_length(G, seed).items():
            if target in nodes:
                current_d = nodes[target]["depth"]
                if current_d == 0 and nodes[target]["is_seed"]:
                    continue
                nodes[target]["depth"] = min(current_d, length) if current_d > 0 else length

    # Ensure every target in edges exists in nodes
    edges_list = []
    for src, tgt, spec in sorted(list(edges_set)):
        if tgt not in nodes:
            nodes[tgt] = {
                "id": tgt,
                "name": tgt,
                "ecosystem": "npm",
                "version": spec if spec and not spec.startswith(("^", "~", ">", "<")) else "unresolved",
                "publish_date": None,
                "maintainers": None,
                "downloads": None,
                "known_cves": [],
                "license": None,
                "description": "Transitive leaf dependency",
                "depth": nodes.get(src, {}).get("depth", 0) + 1,
                "is_seed": False
            }
        edges_list.append({
            "source": src,
            "target": tgt,
            "version_spec": spec
        })

    max_d = max((n["depth"] for n in nodes.values()), default=1)
    timestamp = datetime.now(timezone.utc).isoformat()
    snap_hash = hashlib.sha256(source_name.encode()).hexdigest()[:8]
    snapshot_id = f"rg-manifest-{snap_hash}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"

    return {
        "metadata": {
            "snapshot_id": snapshot_id,
            "schema_version": "1.0",
            "source_type": "package-lock.json",
            "source_name": source_name,
            "timestamp": timestamp,
            "seeds": sorted(seeds),
            "max_depth": max_d,
            "node_count": len(nodes),
            "edge_count": len(edges_list)
        },
        "nodes": list(nodes.values()),
        "edges": edges_list
    }


def parse_cyclonedx_sbom(data: Dict[str, Any], source_name: str = "cyclonedx-sbom.json") -> Dict[str, Any]:
    """
    Parses a CycloneDX SBOM (JSON format, spec 1.2 to 1.6).
    Extracts components and dependency graph (dependsOn).
    """
    if data.get("bomFormat") != "CycloneDX":
        raise ManifestParseError(f"'{source_name}' is not a CycloneDX SBOM (bomFormat is not 'CycloneDX').")

    components = data.get("components", [])
    if not isinstance(components, list):
        raise ManifestParseError(f"CycloneDX SBOM '{source_name}' has missing or non-list 'components'.")

    # Map bom-ref or purl or name to canonical clean component name
    ref_to_id: Dict[str, str] = {}
    nodes: Dict[str, Dict[str, Any]] = {}
    edges_set: Set[Tuple[str, str, str]] = set()

    # Check root component in metadata
    meta = data.get("metadata", {})
    root_comp = meta.get("component")
    root_id = None
    if isinstance(root_comp, dict):
        root_name = root_comp.get("name", "root-app").strip().lower()
        root_ref = root_comp.get("bom-ref") or root_name
        ref_to_id[root_ref] = root_name
        root_id = root_name
        nodes[root_name] = {
            "id": root_name,
            "name": root_name,
            "ecosystem": "npm",
            "version": root_comp.get("version", "1.0.0"),
            "publish_date": None,
            "maintainers": None,
            "downloads": None,
            "known_cves": [],
            "license": None,
            "description": root_comp.get("description") or "Root Application Component",
            "depth": 0,
            "is_seed": True
        }

    for comp in components:
        if not isinstance(comp, dict):
            continue
        raw_name = comp.get("name")
        if not raw_name:
            continue
        clean_name = raw_name.strip().lower()
        bom_ref = comp.get("bom-ref") or clean_name
        ref_to_id[bom_ref] = clean_name
        ref_to_id[clean_name] = clean_name

        # Extract license if available
        lic_str = None
        raw_licenses = comp.get("licenses", [])
        if isinstance(raw_licenses, list) and raw_licenses:
            first_lic = raw_licenses[0]
            if isinstance(first_lic, dict):
                lic_obj = first_lic.get("license", {})
                lic_str = lic_obj.get("id") or lic_obj.get("name")

        nodes[clean_name] = {
            "id": clean_name,
            "name": clean_name,
            "ecosystem": "npm",
            "version": comp.get("version", "unknown"),
            "publish_date": None,
            "maintainers": None,
            "downloads": None,
            "known_cves": [],
            "license": lic_str,
            "description": comp.get("description") or f"Component from {source_name}",
            "depth": 1,
            "is_seed": False
        }

    # Process dependencies array
    raw_dependencies = data.get("dependencies", [])
    if isinstance(raw_dependencies, list):
        for dep_entry in raw_dependencies:
            if not isinstance(dep_entry, dict):
                continue
            parent_ref = dep_entry.get("ref")
            parent_id = ref_to_id.get(parent_ref, parent_ref.strip().lower() if parent_ref else None)
            if not parent_id:
                continue

            for child_ref in dep_entry.get("dependsOn", []):
                child_id = ref_to_id.get(child_ref, child_ref.strip().lower() if child_ref else None)
                if child_id and child_id != parent_id:
                    edges_set.add((parent_id, child_id, "direct"))

    # Compute seeds & depth
    import networkx as nx
    G = nx.DiGraph()
    for n in nodes.keys():
        G.add_node(n)
    for src, tgt, spec in edges_set:
        G.add_edge(src, tgt)

    seeds = [n for n, d in nodes.items() if d.get("is_seed", False)]
    if not seeds:
        # In-degree 0 nodes
        seeds = [n for n in G.nodes() if G.in_degree(n) == 0]
        for s in seeds:
            nodes[s]["is_seed"] = True
            nodes[s]["depth"] = 0

    for seed in seeds:
        for target, length in nx.single_source_shortest_path_length(G, seed).items():
            if target in nodes:
                current_d = nodes[target]["depth"]
                if current_d == 0 and nodes[target]["is_seed"]:
                    continue
                nodes[target]["depth"] = min(current_d, length) if current_d > 0 else length

    edges_list = [
        {"source": src, "target": tgt, "version_spec": spec}
        for src, tgt, spec in sorted(list(edges_set))
    ]

    max_d = max((n["depth"] for n in nodes.values()), default=1)
    timestamp = datetime.now(timezone.utc).isoformat()
    snap_hash = hashlib.sha256(source_name.encode()).hexdigest()[:8]
    snapshot_id = f"rg-cyclonedx-{snap_hash}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"

    return {
        "metadata": {
            "snapshot_id": snapshot_id,
            "schema_version": "1.0",
            "source_type": "cyclonedx",
            "source_name": source_name,
            "timestamp": timestamp,
            "seeds": sorted(seeds),
            "max_depth": max_d,
            "node_count": len(nodes),
            "edge_count": len(edges_list)
        },
        "nodes": list(nodes.values()),
        "edges": edges_list
    }


def parse_manifest_content(
    content: Union[str, bytes],
    filename: str = "manifest.json"
) -> Dict[str, Any]:
    """
    Parses manifest content from uploaded bytes or string.
    Automatically detects format (package-lock.json vs CycloneDX SBOM).
    """
    if isinstance(content, bytes):
        try:
            content_str = content.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ManifestParseError(f"Uploaded file '{filename}' is not valid UTF-8 text.") from e
    else:
        content_str = content

    try:
        data = json.loads(content_str)
    except json.JSONDecodeError as e:
        raise ManifestParseError(f"Uploaded file '{filename}' contains invalid JSON: {e.msg} (line {e.lineno})") from e

    if not isinstance(data, dict):
        raise ManifestParseError(f"Uploaded file '{filename}' root must be a JSON object.")

    # Detection logic
    if data.get("bomFormat") == "CycloneDX":
        return parse_cyclonedx_sbom(data, source_name=filename)

    if "packages" in data or "lockfileVersion" in data or "dependencies" in data:
        return parse_package_lock(data, source_name=filename)

    raise ManifestParseError(
        f"Unrecognized format in '{filename}'. "
        "Please provide an npm 'package-lock.json' or a CycloneDX JSON SBOM."
    )
