from dataclasses import dataclass, field
from typing import Any

from app.analysis.semver import sort_key

# Where a package instance comes from. Only "registry" packages are looked up in OSV by
# name@version; workspace/git/file/tarball packages would produce false matches against
# unrelated public packages that happen to share a name and version.
SOURCE_REGISTRY = "registry"
SOURCE_WORKSPACE = "workspace"
SOURCE_GIT = "git"
SOURCE_FILE = "file"
SOURCE_TARBALL = "tarball"

_GIT_PREFIXES = ("git+", "git:", "git@", "github:", "gitlab:", "bitbucket:", "gist:", "ssh://")


@dataclass
class DependencyNode:
    name: str
    version: str | None
    path: str
    resolved: str | None = None
    integrity: str | None = None
    dependencies: dict[str, str] = field(default_factory=dict)
    optional_dependencies: dict[str, str] = field(default_factory=dict)
    peer_dependencies: dict[str, str] = field(default_factory=dict)
    peer_dependencies_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    dev: bool | None = None
    optional: bool | None = None
    dev_optional: bool | None = None
    is_link: bool = False
    source: str = SOURCE_REGISTRY
    # Dependency names shipped inside this package's own tarball; the lockfile does not
    # list them as separate packages, so they must not be reported as "unresolved".
    bundled_dependencies: frozenset[str] = frozenset()

    @property
    def scannable(self) -> bool:
        return self.source == SOURCE_REGISTRY and not self.is_link and bool(self.version)


def classify_source(resolved: str | None, version: str | None, is_link: bool = False) -> str:
    """Classify where a package came from using only what the lockfile states."""
    if is_link:
        return SOURCE_WORKSPACE
    for value in (resolved, version):
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if lowered.startswith(("file:", "link:", "portal:")):
            return SOURCE_FILE
        if lowered.startswith(_GIT_PREFIXES) or "codeload.github.com" in lowered or "/tarball/" in lowered:
            return SOURCE_GIT
    if isinstance(version, str) and version and sort_key(version) is None:
        # e.g. a v1 lockfile where "version" is a URL
        return SOURCE_TARBALL
    if isinstance(resolved, str) and resolved.startswith(("http://", "https://")):
        if resolved.endswith((".tgz", ".tar.gz")) or "/-/" in resolved:
            return SOURCE_REGISTRY
        return SOURCE_TARBALL
    return SOURCE_REGISTRY


def _lockfile_flag(data: dict[str, Any], key: str) -> bool | None:
    """Read an npm lockfile boolean flag.

    In supported npm lockfile v2/v3 package entries these flags are omitted when
    false. Treat an omitted key as false, but preserve malformed explicit values
    as unknown rather than silently coercing them.
    """
    if key not in data:
        return False
    value = data.get(key)
    return value if isinstance(value, bool) else None


def _bundled(data: dict[str, Any], dependencies: dict[str, Any]) -> frozenset[str]:
    declared = data.get("bundleDependencies", data.get("bundledDependencies"))
    if declared is True:
        return frozenset(dependencies)
    if isinstance(declared, list):
        return frozenset(item for item in declared if isinstance(item, str))
    return frozenset()


def parse_dependency_node(path: str, data: dict[str, Any]) -> DependencyNode:
    """Parse one npm lockfile package entry without guessing missing versions."""
    name = data.get("name")
    if not isinstance(name, str) or not name:
        name = path.rsplit("node_modules/", maxsplit=1)[-1]
    version = data.get("version")
    if version is not None and not isinstance(version, str):
        version = str(version)
    resolved = data.get("resolved") if isinstance(data.get("resolved"), str) else None
    is_link = data.get("link") is True
    dependencies = data.get("dependencies", {}) if isinstance(data.get("dependencies", {}), dict) else {}
    return DependencyNode(
        name=name,
        version=version,
        path=path,
        resolved=resolved,
        integrity=data.get("integrity") if isinstance(data.get("integrity"), str) else None,
        dependencies=dependencies,
        optional_dependencies=data.get("optionalDependencies", {}) if isinstance(data.get("optionalDependencies", {}), dict) else {},
        peer_dependencies=data.get("peerDependencies", {}) if isinstance(data.get("peerDependencies", {}), dict) else {},
        peer_dependencies_meta=data.get("peerDependenciesMeta", {}) if isinstance(data.get("peerDependenciesMeta", {}), dict) else {},
        dev=_lockfile_flag(data, "dev"),
        optional=_lockfile_flag(data, "optional"),
        dev_optional=_lockfile_flag(data, "devOptional"),
        is_link=is_link,
        source=classify_source(resolved, version, is_link),
        bundled_dependencies=_bundled(data, dependencies),
    )


def resolve_dependency_path(package_path: str, dependency_name: str, package_paths: set[str]) -> str | None:
    """Resolve an npm dependency using Node's upward node_modules lookup pattern."""
    current_path = package_path
    while True:
        candidate = f"{current_path}/node_modules/{dependency_name}" if current_path else f"node_modules/{dependency_name}"
        if candidate in package_paths:
            return candidate
        if not current_path:
            break
        if "/node_modules/" in current_path:
            current_path = current_path.rsplit("/node_modules/", maxsplit=1)[0]
        else:
            current_path = ""
    return None
