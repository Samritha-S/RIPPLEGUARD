"""
osv_client.py - Live vulnerability client for OSV.dev (FR-1.3).
Queries https://api.osv.dev/v1/query to retrieve live advisory and CVSS data
with robust vector parsing, qualitative mapping, error handling, and in-memory caching.
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple
import requests

logger = logging.getLogger("RippleGuard.OSVClient")

OSV_API_URL = "https://api.osv.dev/v1/query"

# In-memory session cache: (package_name, ecosystem) -> Optional[float]
_OSV_CACHE: Dict[Tuple[str, str], Optional[float]] = {}


def clear_osv_cache() -> None:
    """Clears the in-memory OSV cache (useful for testing)."""
    _OSV_CACHE.clear()


def parse_cvss_v3_vector(vector_str: str) -> Optional[float]:
    """
    Parses a standard FIRST CVSS v3.0 / v3.1 vector string into a base score (0.0 - 10.0).
    Example vector: 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H' -> 9.8
    """
    if not isinstance(vector_str, str) or not vector_str.startswith("CVSS:3."):
        return None

    try:
        parts = dict(part.split(":") for part in vector_str.split("/") if ":" in part)
        if "CVSS" in parts:
            del parts["CVSS"]

        scope_changed = (parts.get("S") == "C")

        av_weights = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
        ac_weights = {"L": 0.77, "H": 0.44}
        ui_weights = {"N": 0.85, "R": 0.62}
        cia_weights = {"H": 0.56, "L": 0.22, "N": 0.0}

        pr_weights_unchanged = {"N": 0.85, "L": 0.62, "H": 0.27}
        pr_weights_changed = {"N": 0.85, "L": 0.68, "H": 0.50}
        pr_weights = pr_weights_changed if scope_changed else pr_weights_unchanged

        av = av_weights.get(parts.get("AV", "N"), 0.85)
        ac = ac_weights.get(parts.get("AC", "L"), 0.77)
        pr = pr_weights.get(parts.get("PR", "N"), 0.85)
        ui = ui_weights.get(parts.get("UI", "N"), 0.85)

        c = cia_weights.get(parts.get("C", "N"), 0.0)
        i = cia_weights.get(parts.get("I", "N"), 0.0)
        a = cia_weights.get(parts.get("A", "N"), 0.0)

        iss = 1.0 - ((1.0 - c) * (1.0 - i) * (1.0 - a))

        if scope_changed:
            impact = 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)
        else:
            impact = 6.42 * iss

        exploitability = 8.22 * av * ac * pr * ui

        if impact <= 0:
            return 0.0

        if scope_changed:
            raw_score = min(1.08 * (impact + exploitability), 10.0)
        else:
            raw_score = min(impact + exploitability, 10.0)

        # Roundup function per CVSS v3.1 spec
        score = math.ceil(raw_score * 10.0) / 10.0
        return round(min(10.0, max(0.0, score)), 1)
    except Exception as e:
        logger.debug(f"Failed to parse CVSS vector '{vector_str}': {e}")
        return None


def extract_highest_cvss(vulns: List[Dict[str, Any]]) -> Optional[float]:
    """
    Extracts the highest CVSS base score across all vulnerabilities returned by OSV.
    Checks explicit numerical scores, CVSS v3 vectors, and qualitative database severity ratings.
    """
    if not vulns or not isinstance(vulns, list):
        return None

    highest_score: float = 0.0
    found_any = False

    qualitative_map = {
        "CRITICAL": 9.0,
        "HIGH": 7.5,
        "MODERATE": 5.5,
        "MEDIUM": 5.5,
        "LOW": 3.0
    }

    for vuln in vulns:
        if not isinstance(vuln, dict):
            continue

        # 1. Check 'severity' array
        severities = vuln.get("severity", [])
        if isinstance(severities, list):
            for s in severities:
                if not isinstance(s, dict):
                    continue
                score_val = s.get("score")
                if isinstance(score_val, (int, float)):
                    highest_score = max(highest_score, float(score_val))
                    found_any = True
                elif isinstance(score_val, str):
                    if score_val.startswith("CVSS:3."):
                        v_score = parse_cvss_v3_vector(score_val)
                        if v_score is not None:
                            highest_score = max(highest_score, v_score)
                            found_any = True
                    else:
                        try:
                            highest_score = max(highest_score, float(score_val))
                            found_any = True
                        except ValueError:
                            pass

        # 2. Check 'database_specific' qualitative severity if no vector or lower
        db_specific = vuln.get("database_specific", {})
        if isinstance(db_specific, dict):
            db_sev = db_specific.get("severity")
            if isinstance(db_sev, str):
                val = qualitative_map.get(db_sev.upper())
                if val is not None:
                    highest_score = max(highest_score, val)
                    found_any = True

    if found_any and highest_score > 0.0:
        return round(min(10.0, max(0.0, highest_score)), 1)

    return None


def query_osv_package(
    package_name: str,
    ecosystem: str = "npm",
    timeout: float = 4.0,
    session: Optional[requests.Session] = None
) -> Optional[float]:
    """
    Queries OSV.dev for the given package name and ecosystem.
    Returns the highest CVSS score (0.0 - 10.0) if found, else None.
    Results are cached in-memory to prevent repeated network calls.
    Silently catches all exceptions, network timeouts, or errors without crashing.
    """
    clean_pkg = package_name.strip().lower()
    eco_clean = "PyPI" if ecosystem.lower() in ["pypi", "python"] else "npm"
    cache_key = (clean_pkg, eco_clean)

    if cache_key in _OSV_CACHE:
        return _OSV_CACHE[cache_key]

    http = session or requests

    payload = {
        "package": {
            "name": clean_pkg,
            "ecosystem": eco_clean
        }
    }

    try:
        response = http.post(OSV_API_URL, json=payload, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            vulns = data.get("vulns", [])
            score = extract_highest_cvss(vulns)
            _OSV_CACHE[cache_key] = score
            return score
        else:
            logger.debug(f"OSV query returned HTTP {response.status_code} for {clean_pkg}")
            _OSV_CACHE[cache_key] = None
            return None
    except Exception as e:
        logger.warning(f"OSV query failed for {clean_pkg} ({eco_clean}): {e}")
        _OSV_CACHE[cache_key] = None
        return None


OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"


def query_osv_batch(
    package_queries: List[Tuple[str, str]],
    timeout: float = 12.0,
    session: Optional[requests.Session] = None
) -> Dict[Tuple[str, str], Optional[float]]:
    """
    Batch queries OSV.dev for multiple packages in a single network request.
    Populates in-memory cache and returns mapped CVSS scores.
    Silently catches all network timeouts or errors without raising.
    """
    results: Dict[Tuple[str, str], Optional[float]] = {}
    missing_queries: List[Tuple[str, str]] = []

    for pkg, eco in package_queries:
        clean_pkg = pkg.strip().lower()
        eco_clean = "PyPI" if eco.lower() in ["pypi", "python"] else "npm"
        key = (clean_pkg, eco_clean)
        if key in _OSV_CACHE:
            results[key] = _OSV_CACHE[key]
        else:
            missing_queries.append(key)

    if not missing_queries:
        return results

    http = session or requests
    payload = {
        "queries": [
            {"package": {"name": p, "ecosystem": e}}
            for p, e in missing_queries
        ]
    }

    try:
        response = http.post(OSV_BATCH_URL, json=payload, timeout=timeout)
        if response.status_code == 200:
            batch_data = response.json()
            raw_results = batch_data.get("results", [])
            for key, r in zip(missing_queries, raw_results):
                vulns = r.get("vulns", []) if isinstance(r, dict) else []
                score = extract_highest_cvss(vulns)
                _OSV_CACHE[key] = score
                results[key] = score
        else:
            for key in missing_queries:
                _OSV_CACHE[key] = None
                results[key] = None
    except Exception as e:
        logger.warning(f"OSV batch query failed: {e}")
        for key in missing_queries:
            _OSV_CACHE[key] = None
            results[key] = None

    return results

