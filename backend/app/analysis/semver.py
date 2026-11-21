"""Minimal semver ordering used for fix recommendations.

Only what SupplyLens needs: parse ``major[.minor[.patch]][-prerelease][+build]`` and
compare two versions. Anything that is not semver-shaped (git URLs, ``file:`` specs)
returns ``None`` so callers can fall back instead of guessing.
"""
from __future__ import annotations

import re
from typing import Any

_SEMVER = re.compile(
    r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


def sort_key(version: Any) -> tuple | None:
    if not isinstance(version, str):
        return None
    match = _SEMVER.match(version.strip())
    if not match:
        return None
    major, minor, patch, prerelease = match.groups()
    core = (int(major), int(minor or 0), int(patch or 0))
    if prerelease is None:
        return core + ((1,),)  # a release sorts after any of its prereleases
    parts = tuple(
        (0, int(item), "") if item.isdigit() else (1, 0, item)
        for item in prerelease.split(".")
    )
    return core + ((0, parts),)


def compare(left: Any, right: Any) -> int | None:
    a, b = sort_key(left), sort_key(right)
    if a is None or b is None:
        return None
    return (a > b) - (a < b)


def sorted_versions(versions: list[str]) -> list[str]:
    """Semver-ascending; unparsable versions go last in lexical order."""
    parsable = [(sort_key(v), v) for v in versions if sort_key(v) is not None]
    other = sorted(v for v in versions if sort_key(v) is None)
    return [v for _, v in sorted(parsable, key=lambda item: item[0])] + other
