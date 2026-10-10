from typing import Any


def get_direct_dependencies(package_data: dict[str, Any]) -> dict[str, str]:
    """Return direct dependency names mapped to production/development type."""
    direct_dependencies: dict[str, str] = {}
    for name in package_data.get("dependencies", {}):
        direct_dependencies[name] = "production"
    for name in package_data.get("devDependencies", {}):
        direct_dependencies.setdefault(name, "development")
    return direct_dependencies
