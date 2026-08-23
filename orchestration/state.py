"""
Workflow state machine and state management.
Implements explicit states and deterministic transitions.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime


class WorkflowState(str, Enum):
    """Workflow execution states."""
    RECEIVED = "received"
    PLANNING = "planning"
    INVESTIGATING = "investigating"
    ACTION_PROPOSED = "action_proposed"
    SAFETY_CHECK = "safety_check"
    REJECTED = "rejected"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    APPROVED = "approved"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    FAILED = "failed"


class WorkflowStateObject(BaseModel):
    """Complete workflow state for persistence and replay."""
    run_id: str = Field(..., description="Unique run identifier")
    incident_id: str = Field(..., description="Incident being processed")
    current_state: WorkflowState = Field(..., description="Current workflow state")
    
    # Incident and investigation details
    incident: Dict[str, Any] = Field(default_factory=dict, description="Incident description")
    plan: Optional[Dict[str, Any]] = Field(None, description="Planner's investigation plan")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="Gathered evidence")
    
    # Action and verification
    action_proposal: Optional[Dict[str, Any]] = Field(None, description="Proposed remediation action")
    verification_decision: Optional[Dict[str, Any]] = Field(None, description="Safety verification result")
    
    # Execution tracking
    tool_results: List[Dict[str, Any]] = Field(default_factory=list, description="Results from executed tools")
    final_result: Optional[str] = Field(None, description="Final outcome or error message")
    
    # Timestamps and metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    errors: List[str] = Field(default_factory=list, description="Errors encountered during workflow")


class StateTransition:
    """Deterministic state transition rules."""
    
    VALID_TRANSITIONS = {
        WorkflowState.RECEIVED: [WorkflowState.PLANNING, WorkflowState.FAILED],
        WorkflowState.PLANNING: [WorkflowState.INVESTIGATING, WorkflowState.FAILED],
        WorkflowState.INVESTIGATING: [WorkflowState.ACTION_PROPOSED, WorkflowState.NEEDS_MORE_EVIDENCE, WorkflowState.FAILED],
        WorkflowState.ACTION_PROPOSED: [WorkflowState.SAFETY_CHECK, WorkflowState.FAILED],
        WorkflowState.SAFETY_CHECK: [
            WorkflowState.APPROVED,
            WorkflowState.REJECTED,
            WorkflowState.NEEDS_MORE_EVIDENCE,
            WorkflowState.FAILED
        ],
        WorkflowState.NEEDS_MORE_EVIDENCE: [WorkflowState.INVESTIGATING, WorkflowState.FAILED],
        WorkflowState.REJECTED: [WorkflowState.PLANNING, WorkflowState.FAILED],
        WorkflowState.APPROVED: [WorkflowState.EXECUTING, WorkflowState.FAILED],
        WorkflowState.EXECUTING: [WorkflowState.VERIFYING, WorkflowState.FAILED],
        WorkflowState.VERIFYING: [WorkflowState.RESOLVED, WorkflowState.FAILED],
        WorkflowState.RESOLVED: [],
        WorkflowState.FAILED: [],
    }
    
    @classmethod
    def is_valid_transition(cls, from_state: WorkflowState, to_state: WorkflowState) -> bool:
        """Check if a state transition is valid."""
        if from_state not in cls.VALID_TRANSITIONS:
            return False
        return to_state in cls.VALID_TRANSITIONS[from_state]
    
    @classmethod
    def get_error_message(cls, from_state: WorkflowState, to_state: WorkflowState) -> str:
        """Get error message for invalid transition."""
        return f"Invalid transition from {from_state} to {to_state}"
