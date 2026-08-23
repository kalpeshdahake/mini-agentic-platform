"""
Inter-agent communication (A2A) contracts using Pydantic.
All inter-agent communication must use typed/validated messages.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class RiskLevel(str, Enum):
    """Risk level classification for actions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Evidence(BaseModel):
    """Structured evidence with source tracking."""
    id: str = Field(..., description="Unique identifier for evidence")
    source: str = Field(..., description="Source of evidence (e.g., logs, metrics, runbook)")
    service: str = Field(..., description="Service this evidence relates to")
    content: str = Field(..., description="Evidence content/finding")
    timestamp: str = Field(..., description="When evidence was found")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")


class InvestigationRequest(BaseModel):
    """Request from Planner to Investigator Agent."""
    incident_id: str = Field(..., description="Unique incident ID")
    service: str = Field(..., description="Primary affected service")
    environment: str = Field(..., description="Environment (prod, staging, dev)")
    symptoms: List[str] = Field(..., description="List of observed symptoms")
    timeframe: str = Field(..., description="Time range to investigate (e.g., '30 minutes')")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class InvestigationResult(BaseModel):
    """Result from Investigator Agent back to Planner."""
    incident_id: str
    findings: List[str] = Field(..., description="Key findings from investigation")
    evidence: List[Evidence] = Field(..., description="Supporting evidence")
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_next_step: str = Field(..., description="Suggested action or investigation")


class ActionProposal(BaseModel):
    """Action proposal from Infra/Ops Agent."""
    incident_id: str
    action: str = Field(..., description="Action name (e.g., 'restart', 'scale')")
    service: str = Field(..., description="Target service")
    parameters: Dict[str, Any] = Field(..., description="Action parameters")
    reason: str = Field(..., description="Why this action is proposed")
    evidence_ids: List[str] = Field(default_factory=list, description="Supporting evidence IDs")
    expected_outcome: str = Field(..., description="Expected result if executed")


class PolicyCheck(BaseModel):
    """Result of a single policy check."""
    check_name: str
    passed: bool
    reason: str


class VerificationDecision(BaseModel):
    """Decision from Verifier/Safety Agent."""
    incident_id: str
    approved: bool
    risk_level: RiskLevel = Field(..., description="Assessed risk level")
    blast_radius: List[str] = Field(..., description="Services that could be affected")
    policy_checks: List[PolicyCheck] = Field(..., description="Results of policy checks")
    reason: str = Field(..., description="Explanation of decision")
    safer_alternative: Optional[str] = Field(None, description="Suggested safer alternative if rejected")


class ToolCall(BaseModel):
    """Record of a tool call for tracing."""
    tool_name: str
    tool_version: str = "v1"
    input_args: Dict[str, Any]
    output: Dict[str, Any]
    error: Optional[str] = None
    latency_ms: float
    timestamp: str


class AgentStep(BaseModel):
    """Record of an agent processing step."""
    agent_name: str
    step_name: str
    input_redacted: Dict[str, Any]
    output_redacted: Dict[str, Any]
    decision: str
    rejected_alternatives: List[str] = Field(default_factory=list)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    timestamp: str


class ExecutionTrace(BaseModel):
    """Complete trace of workflow execution for replay."""
    run_id: str
    incident_id: str
    workflow_state: str
    agents_executed: List[AgentStep] = Field(default_factory=list)
    final_result: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
