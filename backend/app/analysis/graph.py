from dataclasses import dataclass, field
from enum import Enum

from app.analysis.dependencies import (
    DependencyNode,
    resolve_dependency_path,
    parse_dependency_node,
)

class DependencyType(str,Enum):
    NORMAL = "normal"
    OPTIONAL = "optional"
    PEER = "peer"
    
@dataclass
class DependencyEdge:
    source:str
    target:str
    dependency_type:DependencyType    

@dataclass
class DependencyGraph:
    nodes: dict[str, DependencyNode] = field(
        default_factory=dict
    )

    edges: list[DependencyEdge] = field(
        default_factory=list
    )
    reverse_edges: dict[str, set[str]] = field(
        default_factory=dict
    )    
    unresolved: list[dict[str, str]] = field(
        default_factory=list
    )    
    
def add_edge(
    graph: DependencyGraph,
    source: str,
    target: str,
    dependency_type: DependencyType,
) -> None:
    graph.edges.append(
        DependencyEdge(
            source=source,
            target=target,
            dependency_type=dependency_type,
        )
    )

    graph.reverse_edges.setdefault(
        target,
        set(),
    ).add(source)    
    
def build_dependency_graph(
    packages: dict[str, dict],
) -> DependencyGraph:
    graph = DependencyGraph()

    package_paths = set(packages.keys())

    for path, data in packages.items():
        if not path:
            continue

        node = parse_dependency_node(path,data)

        graph.nodes[path] = node


    for path, node in graph.nodes.items():
        for dependency_name in node.dependencies:
            dependency_path = resolve_dependency_path(
                path,
                dependency_name,
                package_paths,
            )

            if dependency_path:
                add_edge(
                    graph,
                    path,
                    dependency_path,
                    DependencyType.NORMAL,
                    
                )
            else:
                graph.unresolved.append(
                    {
                    "from":path,
                    "dependency":dependency_name,
                    }
                )  
        for dependency_name in node.optional_dependencies:
            dependency_path = resolve_dependency_path(
                path,
                dependency_name,
                package_paths
            )           
            
            if dependency_path:
                    add_edge(
                        graph,
                        path,
                        dependency_path,
                        DependencyType.OPTIONAL,
                    )
        for dependency_name in node.peer_dependencies:
            dependency_path = resolve_dependency_path(
                path,
                dependency_name,
                package_paths,
            )
            if dependency_path:
                    add_edge(
                        graph,
                        path,
                        dependency_path,
                        DependencyType.PEER,
                    )               
    return graph    

  