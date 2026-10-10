from dataclasses import dataclass
from app.analysis.graph import DependencyGraph
from app.analysis.projects import NpmProject
from collections import deque



@dataclass
class ProjectImpact:
    project_path:str
    dependency_type:str
    target:str
    target_name:str
    target_version:str
    path:list[str]

@dataclass
class ImpactResult:
    target_name:str
    target_version:str
    affected_projects:list[ProjectImpact]
    
@dataclass
class RepositoryImpactResult:
    target_name: str
    target_version: str
    affected_projects: list[ProjectImpact]
    projects_analyzed: int    
    
def find_affected_packages(
    graph: DependencyGraph,
    dependency_path: str,
) -> set[str]:
    if dependency_path not in graph.nodes:
        return set()

    affected: set[str] = set()
    pending = [dependency_path]

    while pending:
        current = pending.pop()

        if current in affected:
            continue

        affected.add(current)

        pending.extend(
            graph.reverse_edges.get(current,set())
        )

    return affected

def find_dependency_paths(
    graph: DependencyGraph,
    dependency_path: str,
) -> dict[str, list[str]]:
    if dependency_path not in graph.nodes:
        return {}

    paths: dict[str, list[str]] = {
        dependency_path: [dependency_path]
    }

    queue = deque([dependency_path])

    while queue:
        current = queue.popleft()

        for parent in graph.reverse_edges.get(current, set()):
            if parent in paths:
                continue

            paths[parent] = paths[current] + [parent]
            queue.append(parent)

    return paths
    
    
def find_project_impact(
    graph:DependencyGraph,
    project:NpmProject,
    dependency_path:str,
) -> list[ProjectImpact]:
    affected_packages = find_affected_packages(
        graph,
        dependency_path,
    )
    
    paths = find_dependency_paths(
        graph,
        dependency_path,
    )
    
    impacts:list[ProjectImpact] = []
    
    for dependency in project.dependencies:
        if dependency.dependency_path not in affected_packages:
            continue
        path = paths.get(dependency.dependency_path)
        
        if path is None:
            continue
        target_node = graph.nodes[dependency.dependency_path]        
        impacts.append(
            ProjectImpact(
                project_path=project.root_path,
                dependency_type=dependency.dependency_type,
                target= dependency.dependency_path,
                target_name=target_node.name,
                target_version=target_node.version,
                path=path,
            )
        )
        
    return impacts

def analyze_impact(
    graph:DependencyGraph,
    projects:NpmProject,
    dependency_path:str,
)-> ImpactResult:
    target_node = graph.nodes.get(dependency_path)
    
    if target_node is None:
        return ImpactResult(
            target_name ="",
            target_version="",
            affected_projects=[],
        )

    affected_projects = find_project_impact(
        graph,
        projects,
        dependency_path,
    )
    
    return ImpactResult(
        target_name=target_node.name,
        target_version=target_node.version,
        affected_projects=affected_projects,
    )