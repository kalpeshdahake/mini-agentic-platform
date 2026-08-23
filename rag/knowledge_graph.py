"""
Knowledge graph for service relationships and blast radius analysis.
Supports dependency traversal for identifying affected services.
"""

import json
from typing import Set, List, Dict, Any, Optional
from pathlib import Path


class ServiceDependencyGraph:
    """
    Directed graph representing service relationships.
    Used to calculate blast radius for safety verification.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.services: Dict[str, Dict[str, Any]] = {}
        self.edges: List[tuple] = []
        self.adjacency: Dict[str, Set[str]] = {}
        self._load_infrastructure()
    
    def _load_infrastructure(self) -> None:
        """Load service and dependency data."""
        infra_file = self.data_dir / "infrastructure" / "services.json"
        if not infra_file.exists():
            return
        
        with open(infra_file, 'r') as f:
            infra_data = json.load(f)
        
        # Load services
        for service in infra_data.get("services", []):
            self.services[service["name"]] = {
                "name": service["name"],
                "owner": service.get("owner"),
                "version": service.get("version"),
                "critical": service.get("critical", False),
                "type": service.get("type", "service"),
            }
            self.adjacency[service["name"]] = set()
        
        # Load edges (dependencies)
        for edge in infra_data.get("dependency_graph", {}).get("edges", []):
            source = edge.get("source")
            target = edge.get("target")
            dep_type = edge.get("type", "calls")
            
            self.edges.append((source, target, dep_type))
            if source in self.adjacency:
                self.adjacency[source].add(target)
    
    def get_blast_radius(self, service: str, depth: int = 2) -> Set[str]:
        """
        Calculate blast radius: all services that could be affected if `service` fails.
        Uses reverse dependency traversal (who depends on this service).
        """
        affected = set()
        visited = set()
        
        def traverse(current, remaining_depth):
            if current in visited or remaining_depth == 0:
                return
            
            visited.add(current)
            affected.add(current)
            
            # Find all services that depend on current
            for edge in self.edges:
                if edge[1] == current:  # If current is the target (dependency)
                    dependent = edge[0]  # The service that depends on it
                    if dependent not in visited:
                        traverse(dependent, remaining_depth - 1)
        
        traverse(service, depth)
        affected.discard(service)  # Remove the original service
        return affected
    
    def get_dependencies(self, service: str) -> Set[str]:
        """Get direct dependencies of a service."""
        deps = set()
        for edge in self.edges:
            if edge[0] == service:
                deps.add(edge[1])
        return deps
    
    def is_critical_path(self, service: str) -> bool:
        """Check if service is on a critical path."""
        if not self.services.get(service, {}).get("critical"):
            return False
        
        # Check if multiple services depend on this one
        dependent_count = 0
        for edge in self.edges:
            if edge[1] == service:
                dependent_count += 1
        
        return dependent_count >= 2
    
    def get_owners(self, services: Set[str]) -> Set[str]:
        """Get owners of services in a set."""
        owners = set()
        for service in services:
            owner = self.services.get(service, {}).get("owner")
            if owner:
                owners.add(owner)
        return owners
    
    def visualize_subgraph(self, root_service: str, depth: int = 2) -> Dict[str, Any]:
        """
        Generate a visualization-friendly representation of the dependency subgraph.
        """
        nodes = set()
        edges = []
        visited = set()
        
        def traverse(current, d):
            if current in visited or d == 0:
                return
            
            visited.add(current)
            nodes.add(current)
            
            # Add edges where current is the source
            for edge in self.edges:
                if edge[0] == current:
                    target = edge[1]
                    edges.append({
                        "source": current,
                        "target": target,
                        "type": edge[2],
                    })
                    if target not in visited:
                        traverse(target, d - 1)
        
        traverse(root_service, depth)
        
        return {
            "root": root_service,
            "nodes": [
                {
                    "id": node,
                    **self.services.get(node, {}),
                }
                for node in sorted(nodes)
            ],
            "edges": edges,
        }
