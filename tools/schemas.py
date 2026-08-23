"""
Tool schemas and contracts.
All tools are schema-first and versioned.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from enum import Enum


class ToolVersion(str, Enum):
    """Tool API versions."""
    V1 = "v1"


class ToolErrorEnvelope(BaseModel):
    """Structured error response from tools."""
    success: bool = False
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None


class ToolSuccessEnvelope(BaseModel):
    """Structured success response from tools."""
    success: bool = True
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


# ==================== Tool Input Schemas ====================

class GetLogsRequest(BaseModel):
    """Request to retrieve logs."""
    service: str = Field(..., description="Service name")
    environment: str = Field(..., description="Environment (prod/staging/dev)")
    timeframe: str = Field(..., description="Time range (e.g., '30m', '1h')")
    limit: Optional[int] = Field(1000, description="Max log lines to return")
    filters: Optional[Dict[str, str]] = Field(None, description="Additional log filters")


class GetMetricsRequest(BaseModel):
    """Request to retrieve metrics."""
    service: str = Field(..., description="Service name")
    environment: str = Field(..., description="Environment (prod/staging/dev)")
    metric_names: Optional[List[str]] = Field(None, description="Specific metrics to retrieve")


class SimulateRestartRequest(BaseModel):
    """Request to simulate restarting a service."""
    service: str = Field(..., description="Service to restart")
    environment: str = Field(..., description="Environment (prod/staging/dev)")
    graceful: bool = Field(True, description="Use graceful shutdown")


class SimulateScaleRequest(BaseModel):
    """Request to simulate scaling a service."""
    service: str = Field(..., description="Service to scale")
    environment: str = Field(..., description="Environment (prod/staging/dev)")
    replicas: int = Field(..., ge=1, le=100, description="Target number of replicas")


class GetDependencyGraphRequest(BaseModel):
    """Request to retrieve service dependency graph."""
    environment: str = Field(..., description="Environment (prod/staging/dev)")
    service: Optional[str] = Field(None, description="Root service for subgraph")


# ==================== Tool Output Schemas ====================

class LogLine(BaseModel):
    """Single log line."""
    timestamp: str
    level: str  # INFO, ERROR, WARN
    message: str
    service: str


class GetLogsResponse(BaseModel):
    """Response from get_logs tool."""
    service: str
    environment: str
    timeframe: str
    logs: List[LogLine]
    count: int


class MetricDataPoint(BaseModel):
    """Single metric data point."""
    timestamp: str
    metric_name: str
    value: float
    unit: str


class GetMetricsResponse(BaseModel):
    """Response from get_metrics tool."""
    service: str
    environment: str
    metrics: List[MetricDataPoint]


class ServiceNode(BaseModel):
    """Service node in dependency graph."""
    name: str
    environment: str
    owner: str
    version: str
    instances: int


class ServiceEdge(BaseModel):
    """Edge representing dependency."""
    source: str
    target: str
    dependency_type: str  # "calls", "depends_on", etc.


class GetDependencyGraphResponse(BaseModel):
    """Response from get_dependency_graph tool."""
    services: List[ServiceNode]
    edges: List[ServiceEdge]
    environment: str


class SimulateRestartResponse(BaseModel):
    """Response from simulate_restart tool."""
    service: str
    environment: str
    status: str  # "success", "in_progress", "failed"
    message: str
    instances_restarted: int


class SimulateScaleResponse(BaseModel):
    """Response from simulate_scale tool."""
    service: str
    environment: str
    status: str
    message: str
    current_replicas: int
    target_replicas: int


# ==================== Tool Registry ====================

TOOL_SCHEMAS = {
    "get_logs": {
        "description": "Retrieve logs for a service",
        "version": "v1",
        "input_schema": GetLogsRequest,
        "output_schema": GetLogsResponse,
        "environment_scoped": True,
    },
    "get_metrics": {
        "description": "Retrieve metrics for a service",
        "version": "v1",
        "input_schema": GetMetricsRequest,
        "output_schema": GetMetricsResponse,
        "environment_scoped": True,
    },
    "simulate_restart": {
        "description": "Simulate restarting a service",
        "version": "v1",
        "input_schema": SimulateRestartRequest,
        "output_schema": SimulateRestartResponse,
        "environment_scoped": True,
        "risk_level": "medium",
    },
    "simulate_scale": {
        "description": "Simulate scaling a service",
        "version": "v1",
        "input_schema": SimulateScaleRequest,
        "output_schema": SimulateScaleResponse,
        "environment_scoped": True,
        "risk_level": "medium",
    },
    "get_dependency_graph": {
        "description": "Get service dependency graph for blast radius analysis",
        "version": "v1",
        "input_schema": GetDependencyGraphRequest,
        "output_schema": GetDependencyGraphResponse,
        "environment_scoped": True,
        "risk_level": "low",
    },
}
