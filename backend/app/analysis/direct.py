from typing import Any


def get_direct_dependencies(package_data: dict[str, Any]) -> dict[str, str]:
    """Map manifest dependency names to their declared runtime/development scope."""
    result: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        entries = package_data.get(key, {})
        if not isinstance(entries, dict):
            continue
        scope = {
            "dependencies": "production",
            "devDependencies": "development",
            "optionalDependencies": "optional",
            "peerDependencies": "peer",
        }[key]
        for name in entries:
            if isinstance(name, str):
                result.setdefault(name, scope)
    return result
