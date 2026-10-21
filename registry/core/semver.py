"""
Pheonix Semantic Versioning (SemVer 2.0) Parser & Matcher
Supports exact matches, comparator ranges (>=, <=, >, <, ==), compound expressions, and caret ranges (^).
"""

import re
from typing import Tuple, List

SEMVER_REGEX = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


class InvalidVersionError(Exception):
    pass


def parse_version(v_str: str) -> Tuple[int, int, int]:
    """Parse a version string into (major, minor, patch)."""
    clean_v = v_str.strip()
    match = SEMVER_REGEX.match(clean_v)
    if not match:
        raise InvalidVersionError(f"Invalid SemVer string: '{v_str}'")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings. Returns -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2."""
    p1 = parse_version(v1)
    p2 = parse_version(v2)
    if p1 < p2:
        return -1
    elif p1 > p2:
        return 1
    return 0


def _matches_single_clause(version: str, clause: str) -> bool:
    clause = clause.strip()
    if not clause or clause == "*":
        return True

    # Caret range: ^1.2.3 or ^0.1.2
    if clause.startswith("^"):
        base_v = clause[1:].strip()
        maj, mino, patch = parse_version(base_v)
        # ^1.2.3 -> >=1.2.3 <2.0.0
        # ^0.1.2 -> >=0.1.2 <0.2.0
        # ^0.0.3 -> >=0.0.3 <0.0.4
        if maj > 0:
            upper = f"{maj + 1}.0.0"
        elif mino > 0:
            upper = f"0.{mino + 1}.0"
        else:
            upper = f"0.0.{patch + 1}"
        return compare_versions(version, base_v) >= 0 and compare_versions(version, upper) < 0

    # Comparator prefixes
    for op in (">=", "<=", "==", ">", "<", "="):
        if clause.startswith(op):
            target_v = clause[len(op):].strip()
            cmp = compare_versions(version, target_v)
            if op == ">=":
                return cmp >= 0
            elif op == "<=":
                return cmp <= 0
            elif op in ("==", "="):
                return cmp == 0
            elif op == ">":
                return cmp > 0
            elif op == "<":
                return cmp < 0

    # Default to exact match
    return compare_versions(version, clause) == 0


def matches_constraint(version: str, constraint_str: str) -> bool:
    """
    Check if a version satisfies a constraint expression.
    Multiple comma-separated conditions must all be satisfied.
    Examples: '>=0.1.0, <1.0.0', '^0.1.0', '==0.2.0'
    """
    clauses = [c.strip() for c in constraint_str.split(",") if c.strip()]
    if not clauses:
        return True
    return all(_matches_single_clause(version, c) for c in clauses)
