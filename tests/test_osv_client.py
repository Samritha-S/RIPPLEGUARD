"""
test_osv_client.py - Tests for FR-1.3: Live vulnerability API (OSV.dev).
Verifies CVSS v3 vector parsing, highest severity extraction, mocked API responses,
error/timeout fallback handling, in-memory caching, and downstream scoring integration.
"""

import os
import sys
from unittest.mock import MagicMock
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.osv_client import (
    parse_cvss_v3_vector,
    extract_highest_cvss,
    query_osv_package,
    query_osv_batch,
    clear_osv_cache
)
from src.scoring import compute_composite_criticality
from src.models import WeightingConfig


def test_parse_cvss_v3_vector():
    """Verify mathematical calculation of CVSS v3.1 base score from vector strings."""
    # Critical: Network, Low complexity, No privs, No UI, High C/I/A
    crit_vec = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert parse_cvss_v3_vector(crit_vec) == 9.8

    # Low-Medium (debug ReDoS profile): Network, High complexity, Low Availability
    med_vec = "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:N/A:L"
    assert parse_cvss_v3_vector(med_vec) == 3.7

    # Non-CVSS or malformed
    assert parse_cvss_v3_vector("INVALID_VECTOR") is None
    assert parse_cvss_v3_vector(123) is None
    assert parse_cvss_v3_vector(None) is None


def test_extract_highest_cvss_multiple_vulns():
    """Verify extraction of the maximum CVSS score across multiple vulnerability entries."""
    vulns = [
        {
            "id": "GHSA-1",
            "severity": [
                {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:N/A:L"}  # 3.7
            ]
        },
        {
            "id": "GHSA-2",
            "severity": [
                {"type": "CVSS_V3", "score": 7.5}  # Numerical score 7.5
            ]
        },
        {
            "id": "GHSA-3",
            "severity": [
                {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}  # 9.8
            ]
        }
    ]

    highest = extract_highest_cvss(vulns)
    assert highest == 9.8


def test_extract_highest_cvss_qualitative_fallback():
    """Verify qualitative severity extraction when vector is absent."""
    vulns = [
        {
            "id": "GHSA-QUAL",
            "database_specific": {"severity": "HIGH"}
        }
    ]
    assert extract_highest_cvss(vulns) == 7.5


def test_extract_highest_cvss_empty_or_none():
    """Verify empty or non-vulnerable payloads return None."""
    assert extract_highest_cvss([]) is None
    assert extract_highest_cvss([{"id": "NO-SEV", "severity": []}]) is None
    assert extract_highest_cvss(None) is None


def test_query_osv_package_mocked_success_and_cache():
    """Verify querying OSV.dev with mock session and in-memory cache behavior."""
    clear_osv_cache()
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "vulns": [
            {
                "id": "GHSA-TEST",
                "severity": [
                    {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}
                ]
            }
        ]
    }
    mock_session.post.return_value = mock_response

    # First call: hits session.post
    score1 = query_osv_package("test-pkg", ecosystem="npm", session=mock_session)
    assert score1 == 9.8
    assert mock_session.post.call_count == 1

    # Second call: hits in-memory cache, session.post NOT called again
    score2 = query_osv_package("test-pkg", ecosystem="npm", session=mock_session)
    assert score2 == 9.8
    assert mock_session.post.call_count == 1


def test_query_osv_package_mocked_empty_and_error():
    """Verify silent fallback to None on 404, 500, or timeout/exception."""
    clear_osv_cache()
    mock_session = MagicMock()

    # 1. Non-200 HTTP status
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_session.post.return_value = mock_response
    assert query_osv_package("missing-pkg", ecosystem="npm", session=mock_session) is None

    # 2. Network Exception / Timeout
    clear_osv_cache()
    mock_session.post.side_effect = requests.exceptions.Timeout("Connection timed out")
    assert query_osv_package("timeout-pkg", ecosystem="npm", session=mock_session) is None


def test_scoring_fallback_vs_live_osv():
    """Verify compute_composite_criticality uses live_cvss when provided and defaults when None."""
    dummy_metrics = {"in_degree": 5, "transitive_dependents_count": 8}

    # 1. live_cvss provided
    score_live = compute_composite_criticality(
        package_name="test-lib",
        metrics=dummy_metrics,
        max_in_degree=10,
        max_transitive=10,
        live_cvss=9.5
    )
    assert score_live.cvss == 9.5
    assert score_live.severity_source == "live_osv"
    assert score_live.tier == "CRITICAL"

    # 2. live_cvss is None -> falls back to curated/default baseline
    score_fallback = compute_composite_criticality(
        package_name="test-lib",
        metrics=dummy_metrics,
        max_in_degree=10,
        max_transitive=10,
        live_cvss=None
    )
    assert score_fallback.cvss == 1.0  # default baseline
    assert score_fallback.severity_source == "default"


def test_query_osv_batch_mocked():
    """Verify batch querying OSV.dev endpoint with multiple packages."""
    clear_osv_cache()
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "vulns": [
                    {"id": "V1", "severity": [{"type": "CVSS_V3", "score": 8.5}]}
                ]
            },
            {
                "vulns": []
            }
        ]
    }
    mock_session.post.return_value = mock_response

    queries = [("pkg-a", "npm"), ("pkg-b", "npm")]
    res = query_osv_batch(queries, session=mock_session)

    assert res[("pkg-a", "npm")] == 8.5
    assert res[("pkg-b", "npm")] is None
    assert mock_session.post.call_count == 1

    # Calling again should use in-memory cache
    res2 = query_osv_batch(queries, session=mock_session)
    assert res2[("pkg-a", "npm")] == 8.5
    assert mock_session.post.call_count == 1

