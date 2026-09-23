from typing import Any


def get_direct_dependencies(
    package_data: dict[str, Any],
) -> dict[str, str]:
    direct_dependencies: dict[str, str] = {}

    for name,_ in package_data.get(
        "dependencies", {}
    ).items():
        direct_dependencies[name] = "production"

    for name,_ in package_data.get(
        "devDependencies", {}
    ).items():
        direct_dependencies[name] = "development"

    return direct_dependencies