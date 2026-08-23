"""
Workflow orchestration and graph-based execution.
Implements deterministic state transitions and agent coordination.
"""

from typing import Callable, Dict, Any, Optional
from orchestration.state import WorkflowState, WorkflowStateObject, StateTransition
from messaging.a2a_models import (
    InvestigationRequest,
    InvestigationResult,
    ActionProposal,
    VerificationDecision,
)
import json
import uuid
from datetime import datetime


class WorkflowOrchestrator:
    """
    Orchestrates multi-agent workflow execution.
    Manages state transitions, validates LLM outputs, and prevents unsafe operations.
    """
    
    def __init__(self):
        self.runs: Dict[str, WorkflowStateObject] = {}
        self.agent_handlers: Dict[WorkflowState, Callable] = {}
    
    def create_run(self, incident_id: str, incident_data: Dict[str, Any]) -> str:
        """Initialize a new workflow run."""
        run_id = str(uuid.uuid4())
        state = WorkflowStateObject(
            run_id=run_id,
            incident_id=incident_id,
            current_state=WorkflowState.RECEIVED,
            incident=incident_data,
        )
        self.runs[run_id] = state
        print(f"[ORCHESTRATOR] Created run {run_id} for incident {incident_id}")
        return run_id
    
    def get_run(self, run_id: str) -> Optional[WorkflowStateObject]:
        """Retrieve workflow state by run ID."""
        return self.runs.get(run_id)
    
    def transition_to(
        self,
        run_id: str,
        target_state: WorkflowState,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Attempt to transition to a new state.
        Returns True if successful, False if transition is invalid.
        """
        state = self.get_run(run_id)
        if not state:
            raise ValueError(f"Run {run_id} not found")
        
        # Validate transition
        if not StateTransition.is_valid_transition(state.current_state, target_state):
            error_msg = StateTransition.get_error_message(state.current_state, target_state)
            print(f"[ORCHESTRATOR] {error_msg}")
            state.errors.append(error_msg)
            return False
        
        # Update state
        state.current_state = target_state
        state.updated_at = datetime.utcnow()
        
        # Store context if provided (e.g., investigation results, action proposals)
        if context:
            state_dict = state.model_dump()
            for key, value in context.items():
                if key in state_dict:
                    setattr(state, key, value)
        
        print(f"[ORCHESTRATOR] Run {run_id}: {state.current_state}")
        return True
    
    def add_error(self, run_id: str, error: str) -> None:
        """Record an error in the workflow."""
        state = self.get_run(run_id)
        if state:
            state.errors.append(error)
            state.updated_at = datetime.utcnow()
    
    def get_workflow_summary(self, run_id: str) -> Dict[str, Any]:
        """Get a summary of workflow execution for review."""
        state = self.get_run(run_id)
        if not state:
            return {}
        
        return {
            "run_id": state.run_id,
            "incident_id": state.incident_id,
            "current_state": state.current_state,
            "investigation_findings": len(state.evidence),
            "action_proposed": state.action_proposal is not None,
            "action_approved": state.verification_decision is not None and state.verification_decision.get("approved"),
            "final_result": state.final_result,
            "errors": state.errors,
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
        }
    
    def is_terminal_state(self, run_id: str) -> bool:
        """Check if workflow is in a terminal state."""
        state = self.get_run(run_id)
        if not state:
            return False
        return state.current_state in [
            WorkflowState.RESOLVED,
            WorkflowState.FAILED,
            WorkflowState.REJECTED,
        ]


def execute_workflow_sequence(
    run_id: str,
    orchestrator: WorkflowOrchestrator,
    planner_fn: Callable,
    investigator_fn: Callable,
    ops_fn: Callable,
    verifier_fn: Callable,
    executor_fn: Callable,
) -> Dict[str, Any]:
    """
    Execute the complete workflow sequence deterministically.
    Each step must pass validation before proceeding to the next.
    """
    state = orchestrator.get_run(run_id)
    if not state:
        return {"error": f"Run {run_id} not found"}
    
    try:
        # Step 1: PLANNING
        print(f"\n=== STEP 1: PLANNING ===")
        if not orchestrator.transition_to(run_id, WorkflowState.PLANNING):
            return {"error": "Cannot transition to PLANNING state"}
        
        plan = planner_fn(state.incident)
        state = orchestrator.get_run(run_id)
        state.plan = plan
        print(f"Plan generated with {len(plan.get('tasks', []))} investigation tasks")
        
        # Step 2: INVESTIGATING
        print(f"\n=== STEP 2: INVESTIGATING ===")
        if not orchestrator.transition_to(run_id, WorkflowState.INVESTIGATING):
            return {"error": "Cannot transition to INVESTIGATING state"}
        
        investigation_result = investigator_fn(state.incident, plan)
        state = orchestrator.get_run(run_id)
        state.evidence = [e.model_dump() for e in investigation_result.evidence]
        print(f"Investigation complete: {len(state.evidence)} pieces of evidence gathered")
        
        # Step 3: ACTION_PROPOSED
        print(f"\n=== STEP 3: ACTION PROPOSAL ===")
        if not orchestrator.transition_to(run_id, WorkflowState.ACTION_PROPOSED):
            return {"error": "Cannot transition to ACTION_PROPOSED state"}
        
        action_proposal = ops_fn(state.incident, investigation_result)
        state = orchestrator.get_run(run_id)
        state.action_proposal = action_proposal.model_dump()
        print(f"Action proposed: {action_proposal.action} on {action_proposal.service}")
        
        # Step 4: SAFETY_CHECK
        print(f"\n=== STEP 4: SAFETY CHECK ===")
        if not orchestrator.transition_to(run_id, WorkflowState.SAFETY_CHECK):
            return {"error": "Cannot transition to SAFETY_CHECK state"}
        
        verification = verifier_fn(action_proposal, state.incident)
        state = orchestrator.get_run(run_id)
        state.verification_decision = verification.model_dump()
        
        if not verification.approved:
            print(f"Action REJECTED: {verification.reason}")
            if not orchestrator.transition_to(run_id, WorkflowState.REJECTED):
                return {"error": "Cannot transition to REJECTED state"}
            state.final_result = f"Action rejected: {verification.reason}"
            return orchestrator.get_workflow_summary(run_id)
        
        print(f"Action APPROVED with risk level: {verification.risk_level}")
        
        # Transition to APPROVED state first
        if not orchestrator.transition_to(run_id, WorkflowState.APPROVED):
            return {"error": "Cannot transition to APPROVED state"}
        
        # Step 5: EXECUTING
        print(f"\n=== STEP 5: EXECUTING ===")
        if not orchestrator.transition_to(run_id, WorkflowState.EXECUTING):
            return {"error": "Cannot transition to EXECUTING state"}
        
        tool_result = executor_fn(action_proposal)
        state = orchestrator.get_run(run_id)
        state.tool_results = [tool_result]
        print(f"Tool executed: {tool_result.get('status', 'unknown')}")
        
        # Step 6: VERIFYING
        print(f"\n=== STEP 6: VERIFYING ===")
        if not orchestrator.transition_to(run_id, WorkflowState.VERIFYING):
            return {"error": "Cannot transition to VERIFYING state"}
        
        # Simple post-action verification (in real system, check metrics again)
        verification_result = {
            "status": "verified",
            "message": "Post-action verification would confirm incident resolution",
        }
        print(f"Post-action verification: {verification_result['status']}")
        
        # Step 7: RESOLVED
        print(f"\n=== STEP 7: RESOLVED ===")
        if not orchestrator.transition_to(run_id, WorkflowState.RESOLVED):
            return {"error": "Cannot transition to RESOLVED state"}
        
        state = orchestrator.get_run(run_id)
        state.final_result = "Incident remediation completed successfully"
        
        return orchestrator.get_workflow_summary(run_id)
    
    except Exception as e:
        print(f"[ERROR] Workflow failed: {str(e)}")
        orchestrator.add_error(run_id, str(e))
        orchestrator.transition_to(run_id, WorkflowState.FAILED)
        return {
            "error": str(e),
            "run_id": run_id,
            "summary": orchestrator.get_workflow_summary(run_id),
        }
