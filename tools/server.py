"""
Tool server and implementation layer.
All infrastructure access goes through this abstraction.
No direct SDK/database access allowed.
"""

import json
from typing import Dict, Any, Optional
from tools.schemas import (
    GetLogsRequest,
    GetMetricsRequest,
    SimulateRestartRequest,
    SimulateScaleRequest,
    GetDependencyGraphRequest,
    GetLogsResponse,
    GetMetricsResponse,
    GetDependencyGraphResponse,
    SimulateRestartResponse,
    SimulateScaleResponse,
    LogLine,
    MetricDataPoint,
    ServiceNode,
    ServiceEdge,
)
from pathlib import Path


class ToolServer:
    """Local tool server with schema-first tool implementations."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self._prepare_data_cache()
    
    def _prepare_data_cache(self):
        """Load data files into memory for fast retrieval."""
        # Load logs
        logs_file = self.data_dir / "logs" / "payment_service.log"
        self.logs_cache = {}
        if logs_file.exists():
            with open(logs_file, 'r') as f:
                self.logs_cache[("payment-service", "prod")] = f.readlines()
        
        # Load metrics
        metrics_file = self.data_dir / "metrics" / "metrics.json"
        self.metrics_cache = {}
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                self.metrics_cache = json.load(f).get("metrics", [])
        
        # Load infrastructure
        infra_file = self.data_dir / "infrastructure" / "services.json"
        self.infrastructure_cache = {}
        if infra_file.exists():
            with open(infra_file, 'r') as f:
                self.infrastructure_cache = json.load(f)
    
    def validate_environment_scope(self, environment: str) -> bool:
        """Validate that environment is allowed."""
        allowed = ["prod", "staging", "dev"]
        return environment in allowed
    
    def get_logs(self, request: GetLogsRequest) -> GetLogsResponse:
        """Retrieve logs for a service."""
        # Validate environment
        if not self.validate_environment_scope(request.environment):
            raise ValueError(f"Invalid environment: {request.environment}")
        
        # Load logs from cache
        key = (request.service, request.environment)
        logs_text = self.logs_cache.get(key, [])
        
        # Parse log lines
        log_lines = []
        for line in logs_text:
            if line.strip():
                parts = line.strip().split(' ', 3)
                if len(parts) >= 4:
                    log_lines.append(LogLine(
                        timestamp=parts[0],
                        level=parts[1],
                        message=' '.join(parts[3:]),
                        service=request.service,
                    ))
        
        # Apply limit
        if request.limit:
            log_lines = log_lines[-request.limit:]
        
        return GetLogsResponse(
            service=request.service,
            environment=request.environment,
            timeframe=request.timeframe,
            logs=log_lines,
            count=len(log_lines),
        )
    
    def get_metrics(self, request: GetMetricsRequest) -> GetMetricsResponse:
        """Retrieve metrics for a service."""
        # Validate environment
        if not self.validate_environment_scope(request.environment):
            raise ValueError(f"Invalid environment: {request.environment}")
        
        # Filter metrics by service
        relevant_metrics = [
            m for m in self.metrics_cache
            if m.get("service") == request.service
        ]
        
        # Convert to structured format
        metric_points = []
        for m in relevant_metrics:
            # Extract the requested metrics or all if not specified
            if request.metric_names:
                for metric_name in request.metric_names:
                    if metric_name in m:
                        metric_points.append(MetricDataPoint(
                            timestamp=m["timestamp"],
                            metric_name=metric_name,
                            value=m[metric_name],
                            unit="various",
                        ))
            else:
                # Return all available metrics
                for key, value in m.items():
                    if key not in ["timestamp", "service"] and isinstance(value, (int, float)):
                        metric_points.append(MetricDataPoint(
                            timestamp=m["timestamp"],
                            metric_name=key,
                            value=value,
                            unit="various",
                        ))
        
        return GetMetricsResponse(
            service=request.service,
            environment=request.environment,
            metrics=metric_points,
        )
    
    def get_dependency_graph(
        self, request: GetDependencyGraphRequest
    ) -> GetDependencyGraphResponse:
        """Retrieve service dependency graph."""
        # Validate environment
        if not self.validate_environment_scope(request.environment):
            raise ValueError(f"Invalid environment: {request.environment}")
        
        infra = self.infrastructure_cache
        
        # Convert services to nodes
        service_nodes = []
        for svc in infra.get("services", []):
            service_nodes.append(ServiceNode(
                name=svc["name"],
                environment=request.environment,
                owner=svc.get("owner", "unknown"),
                version=svc.get("version", "unknown"),
                instances=svc.get("replicas", 1),
            ))
        
        # Convert dependencies to edges
        edges = []
        for edge in infra.get("dependency_graph", {}).get("edges", []):
            edges.append(ServiceEdge(
                source=edge["source"],
                target=edge["target"],
                dependency_type=edge.get("type", "calls"),
            ))
        
        return GetDependencyGraphResponse(
            services=service_nodes,
            edges=edges,
            environment=request.environment,
        )
    
    def simulate_restart(self, request: SimulateRestartRequest) -> SimulateRestartResponse:
        """Simulate restarting a service."""
        # Validate environment
        if not self.validate_environment_scope(request.environment):
            raise ValueError(f"Invalid environment: {request.environment}")
        
        # In a real implementation, this would coordinate with infrastructure
        # For now, return a simulated success
        return SimulateRestartResponse(
            service=request.service,
            environment=request.environment,
            status="success",
            message=f"Simulated restart of {request.service} completed successfully",
            instances_restarted=self._get_service_replicas(request.service),
        )
    
    def simulate_scale(self, request: SimulateScaleRequest) -> SimulateScaleResponse:
        """Simulate scaling a service."""
        # Validate environment
        if not self.validate_environment_scope(request.environment):
            raise ValueError(f"Invalid environment: {request.environment}")
        
        current = self._get_service_replicas(request.service)
        
        return SimulateScaleResponse(
            service=request.service,
            environment=request.environment,
            status="success",
            message=f"Scaled {request.service} from {current} to {request.replicas} replicas",
            current_replicas=current,
            target_replicas=request.replicas,
        )
    
    def _get_service_replicas(self, service_name: str) -> int:
        """Get current replica count for a service."""
        for svc in self.infrastructure_cache.get("services", []):
            if svc["name"] == service_name:
                return svc.get("replicas", 1)
        return 1
