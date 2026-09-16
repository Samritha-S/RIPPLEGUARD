"""
test_manifest_parser.py - Unit and regression tests for manifest and SBOM ingestion (Phase B1 / FR-1.1).
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.manifest_parser import (
    parse_package_lock,
    parse_cyclonedx_sbom,
    parse_manifest_content,
    ManifestParseError
)
from src.graph_builder import build_dependency_graph, compute_structural_metrics
from src.scoring import compute_composite_criticality
from src.fix_consolidator import consolidate_fixes


SAMPLE_PACKAGE_LOCK_V3 = {
    "name": "sample-auth-service",
    "version": "1.0.0",
    "lockfileVersion": 3,
    "packages": {
        "": {
            "name": "sample-auth-service",
            "version": "1.0.0",
            "dependencies": {
                "jsonwebtoken": "^9.0.0",
                "bcrypt": "^5.1.0"
            }
        },
        "node_modules/jsonwebtoken": {
            "version": "9.0.2",
            "license": "MIT",
            "dependencies": {
                "jws": "^3.2.2",
                "ms": "^2.1.3"
            }
        },
        "node_modules/bcrypt": {
            "version": "5.1.1",
            "license": "BSD-3-Clause",
            "dependencies": {
                "node-addon-api": "^5.0.0"
            }
        },
        "node_modules/jws": {
            "version": "3.2.2",
            "license": "MIT",
            "dependencies": {
                "jwa": "^1.4.1"
            }
        },
        "node_modules/jwa": {
            "version": "1.4.1",
            "license": "MIT",
            "dependencies": {
                "buffer-equal-constant-time": "1.0.1"
            }
        },
        "node_modules/buffer-equal-constant-time": {
            "version": "1.0.1",
            "license": "BSD-3-Clause"
        },
        "node_modules/ms": {
            "version": "2.1.3",
            "license": "MIT"
        },
        "node_modules/node-addon-api": {
            "version": "5.1.0",
            "license": "MIT"
        }
    }
}

SAMPLE_CYCLONEDX_SBOM = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.4",
    "version": 1,
    "metadata": {
        "component": {
            "name": "payment-gateway",
            "version": "2.4.0",
            "type": "application",
            "bom-ref": "app-root"
        }
    },
    "components": [
        {
            "name": "stripe",
            "version": "12.0.0",
            "bom-ref": "stripe-ref",
            "licenses": [{"license": {"id": "Apache-2.0"}}]
        },
        {
            "name": "crypto-js",
            "version": "4.2.0",
            "bom-ref": "crypto-ref",
            "licenses": [{"license": {"id": "MIT"}}]
        },
        {
            "name": "tslib",
            "version": "2.6.2",
            "bom-ref": "tslib-ref",
            "licenses": [{"license": {"id": "0BSD"}}]
        }
    ],
    "dependencies": [
        {
            "ref": "app-root",
            "dependsOn": ["stripe-ref", "crypto-ref"]
        },
        {
            "ref": "stripe-ref",
            "dependsOn": ["tslib-ref"]
        }
    ]
}


def test_parse_package_lock_v3():
    """Verify parsing of modern npm lockfile (v3) structure."""
    graph_data = parse_package_lock(SAMPLE_PACKAGE_LOCK_V3, source_name="package-lock.json")

    assert "metadata" in graph_data
    assert graph_data["metadata"]["source_type"] == "package-lock.json"
    assert graph_data["metadata"]["node_count"] == 8
    assert graph_data["metadata"]["edge_count"] == 7

    nodes_by_id = {n["id"]: n for n in graph_data["nodes"]}
    assert "jsonwebtoken" in nodes_by_id
    assert nodes_by_id["jsonwebtoken"]["version"] == "9.0.2"
    assert nodes_by_id["jsonwebtoken"]["license"] == "MIT"
    assert nodes_by_id["jsonwebtoken"]["is_seed"] is True

    assert "ms" in nodes_by_id
    assert nodes_by_id["ms"]["is_seed"] is False
    assert nodes_by_id["ms"]["depth"] == 1  # 1 hop from seed jsonwebtoken

    # Check edges
    edges = [(e["source"], e["target"]) for e in graph_data["edges"]]
    assert ("sample-auth-service", "jsonwebtoken") in edges
    assert ("jsonwebtoken", "ms") in edges
    assert ("jsonwebtoken", "jws") in edges
    assert ("jws", "jwa") in edges


def test_parse_cyclonedx_sbom():
    """Verify parsing of CycloneDX JSON SBOM."""
    graph_data = parse_cyclonedx_sbom(SAMPLE_CYCLONEDX_SBOM, source_name="bom.json")

    assert graph_data["metadata"]["source_type"] == "cyclonedx"
    assert graph_data["metadata"]["node_count"] == 4
    assert graph_data["metadata"]["edge_count"] == 3

    nodes_by_id = {n["id"]: n for n in graph_data["nodes"]}
    assert "payment-gateway" in nodes_by_id
    assert nodes_by_id["payment-gateway"]["is_seed"] is True
    assert "stripe" in nodes_by_id
    assert nodes_by_id["stripe"]["license"] == "Apache-2.0"

    edges = [(e["source"], e["target"]) for e in graph_data["edges"]]
    assert ("payment-gateway", "stripe") in edges
    assert ("payment-gateway", "crypto-js") in edges
    assert ("stripe", "tslib") in edges


def test_auto_detection_and_string_bytes_input():
    """Verify parse_manifest_content detects format and handles both bytes and strings."""
    json_bytes = json.dumps(SAMPLE_PACKAGE_LOCK_V3).encode("utf-8")
    parsed_bytes = parse_manifest_content(json_bytes, filename="my-lock.json")
    assert parsed_bytes["metadata"]["source_type"] == "package-lock.json"

    json_str = json.dumps(SAMPLE_CYCLONEDX_SBOM)
    parsed_str = parse_manifest_content(json_str, filename="cyclonedx.json")
    assert parsed_str["metadata"]["source_type"] == "cyclonedx"


def test_malformed_manifest_error_handling():
    """Verify graceful ManifestParseError on invalid JSON or missing fields."""
    with pytest.raises(ManifestParseError) as exc_info:
        parse_manifest_content("this is not json {", filename="bad.json")
    assert "invalid JSON" in str(exc_info.value)

    with pytest.raises(ManifestParseError) as exc_info:
        parse_manifest_content('{"unknownKey": 123}', filename="empty.json")
    assert "Unrecognized format" in str(exc_info.value)


def test_end_to_end_pipeline_with_uploaded_manifest():
    """Verify uploaded graph runs end-to-end through graph_builder, metrics, scoring, and consolidation."""
    graph_data = parse_package_lock(SAMPLE_PACKAGE_LOCK_V3)

    # 1. Build NetworkX DiGraph
    G = build_dependency_graph(graph_data)
    assert G.number_of_nodes() == 8
    assert G.number_of_edges() == 7

    # 2. Compute Structural Metrics
    metrics = compute_structural_metrics(G)
    assert len(metrics) == 8
    assert metrics["ms"]["in_degree"] == 1  # jsonwebtoken depends on ms
    assert metrics["ms"]["transitive_dependents_count"] == 2  # jsonwebtoken and sample-auth-service

    # 3. Criticality Scoring
    max_in = max(m["in_degree"] for m in metrics.values())
    max_tr = max(m["transitive_dependents_count"] for m in metrics.values())
    scores = {n: compute_composite_criticality(n, metrics[n], max_in, max_tr) for n in G.nodes()}

    assert len(scores) == 8
    for n, sc in scores.items():
        assert 0.0 <= sc.score <= 100.0
        assert sc.tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

    # In our curated CVSS dict, ms has CVSS 3.7; buffer-equal-constant-time has default fallback CVSS 1.0
    assert scores["ms"].cvss == 3.7
    assert scores["buffer-equal-constant-time"].cvss == 1.0  # FR-1.6 default fallback applied cleanly

    # 4. Fix Consolidation
    report = consolidate_fixes(G, scores, metrics)
    assert report is not None
    assert isinstance(report.headline_stat, str)


def test_parse_package_lock_v1():
    """Verify parsing of legacy npm lockfile (v1) structure with nested dependencies."""
    v1_lock = {
        "name": "legacy-app",
        "version": "1.0.0",
        "lockfileVersion": 1,
        "dependencies": {
            "morgan": {
                "version": "1.10.0",
                "dependencies": {
                    "basic-auth": {
                        "version": "2.0.1"
                    }
                }
            }
        }
    }
    graph_data = parse_package_lock(v1_lock, source_name="v1-lock.json")
    assert graph_data["metadata"]["source_type"] == "package-lock.json"
    assert graph_data["metadata"]["node_count"] == 3
    nodes_by_id = {n["id"]: n for n in graph_data["nodes"]}
    assert "legacy-app" in nodes_by_id
    assert "morgan" in nodes_by_id
    assert "basic-auth" in nodes_by_id
    edges = [(e["source"], e["target"]) for e in graph_data["edges"]]
    assert ("legacy-app", "morgan") in edges
    assert ("morgan", "basic-auth") in edges


if __name__ == "__main__":
    test_parse_package_lock_v3()
    print("test_parse_package_lock_v3 PASSED")
    test_parse_package_lock_v1()
    print("test_parse_package_lock_v1 PASSED")
    test_parse_cyclonedx_sbom()
    print("test_parse_cyclonedx_sbom PASSED")
    test_auto_detection_and_string_bytes_input()
    print("test_auto_detection_and_string_bytes_input PASSED")
    test_malformed_manifest_error_handling()
    print("test_malformed_manifest_error_handling PASSED")
    test_end_to_end_pipeline_with_uploaded_manifest()
    print("test_end_to_end_pipeline_with_uploaded_manifest PASSED")
