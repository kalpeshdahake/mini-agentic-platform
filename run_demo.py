"""
Main demo runner for Mini Agentic AI Platform.
This script orchestrates the complete workflow from incident detection to remediation.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from orchestration.graph import WorkflowOrchestrator, execute_workflow_sequence
from agents.base import PlannerAgent, InvestigatorAgent, OpsAgent, VerifierAgent
from tools.server import ToolServer
from llm_client import OllamaClient


def simulate_tool_executor(action_proposal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a simulated infrastructure action.
    In production, this would call actual infrastructure APIs.
    """
    action = action_proposal.get("action")
    service = action_proposal.get("service")
    
    print(f"\n[EXECUTOR] Executing action: {action} on {service}")
    
    # Simulate execution
    if action == "scale":
        params = action_proposal.get("parameters", {})
        return {
            "tool_name": "simulate_scale",
            "success": True,
            "service": service,
            "status": "success",
            "message": f"Scaled {service} to {params.get('target_replicas', 6)} replicas",
            "instances_affected": params.get("target_replicas", 6),
        }
    elif action == "restart":
        return {
            "tool_name": "simulate_restart",
            "success": True,
            "service": service,
            "status": "success",
            "message": f"Restarted {service}",
            "instances_affected": 1,
        }
    else:
        return {
            "tool_name": "unknown",
            "success": False,
            "error": f"Unknown action: {action}",
        }


def main():
    """Run the complete demo workflow."""
    
    print("=" * 80)
    print("MINI AGENTIC AI PLATFORM - DEMO")
    print("=" * 80)
    
    # ========== STEP 1: Initialize ==========
    print("\n[INIT] Initializing platform components...")
    
    # Load incident data
    incident_file = Path(__file__).parent / "data" / "incident.json"
    if not incident_file.exists():
        print(f"[ERROR] Incident file not found: {incident_file}")
        return
    
    with open(incident_file, 'r') as f:
        incident = json.load(f)
    
    # Initialize components
    llm_client = OllamaClient()
    orchestrator = WorkflowOrchestrator()
    tool_server = ToolServer(data_dir=str(Path(__file__).parent / "data"))
    planner = PlannerAgent(llm_client=llm_client)
    investigator = InvestigatorAgent(tool_server)
    ops = OpsAgent(llm_client=llm_client)
    verifier = VerifierAgent()
    
    print(f"[INIT] Platform initialized")
    print(f"[INIT] Local LLM: {llm_client.model} ({'available' if llm_client.enabled else 'fallback mode'})")
    print(f"[INIT] Incident: {incident['description']}")
    print(f"[INIT] Affected Service: {incident['affected_service']}")
    print(f"[INIT] Environment: {incident['environment']}")
    
    # ========== STEP 2: Create workflow run ==========
    print("\n[WORKFLOW] Creating new run...")
    run_id = orchestrator.create_run(incident['incident_id'], incident)
    
    # ========== STEP 3: Execute workflow ==========
    print(f"\n[WORKFLOW] Executing multi-agent workflow for run {run_id}...")
    print("=" * 80)
    
    # Define agent functions that match the expected signatures
    def plan_fn(inc):
        return planner.plan(inc)
    
    def investigate_fn(inc, plan):
        return investigator.investigate(inc, plan)
    
    def ops_fn(inc, investigation):
        return ops.propose_action(inc, investigation)
    
    def verifier_fn(action, inc):
        # Build simple dependency graph for verification
        dep_graph = {}
        return verifier.verify(action, inc, dep_graph)
    
    def execute_fn(action):
        return simulate_tool_executor(action.model_dump())
    
    # Execute the complete workflow
    result = execute_workflow_sequence(
        run_id=run_id,
        orchestrator=orchestrator,
        planner_fn=plan_fn,
        investigator_fn=investigate_fn,
        ops_fn=ops_fn,
        verifier_fn=verifier_fn,
        executor_fn=execute_fn,
    )

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    state = orchestrator.get_run(run_id)
    report = {
        "run_id": run_id,
        "incident": incident,
        "llm": {
            "provider": "Ollama",
            "model": llm_client.model,
            "available": llm_client.enabled,
            "fallback_used": not llm_client.enabled,
        },
        "rag": {
            "embedding_model": "all-MiniLM-L6-v2 or hash-simulator fallback",
            "vector_database": "FAISS",
        },
        "workflow_summary": result,
        "state": state.model_dump(mode="json") if state else None,
    }
    report_path = output_dir / f"run_{run_id}.json"
    with open(report_path, "w") as output_file:
        json.dump(report, output_file, indent=2)
    print(f"[OUTPUT] Report saved to: {report_path}")
    
    # ========== STEP 4: Display results ==========
    print("\n" + "=" * 80)
    print("WORKFLOW EXECUTION SUMMARY")
    print("=" * 80)
    
    print(f"\nRun ID: {result.get('run_id')}")
    print(f"Incident ID: {result.get('incident_id')}")
    print(f"Final State: {result.get('current_state')}")
    print(f"Final Result: {result.get('final_result')}")
    print(f"Errors: {len(result.get('errors', []))} errors detected")
    
    if result.get('errors'):
        print("\nErrors:")
        for error in result['errors']:
            print(f"  - {error}")
    
    # ========== STEP 5: Display execution trace ==========
    print("\n" + "=" * 80)
    print("DETAILED EXECUTION TRACE")
    print("=" * 80)
    
    state = orchestrator.get_run(run_id)
    if state:
        print(f"\nIncident: {state.incident.get('description')}")
        print(f"\nInvestigation Plan:")
        if state.plan:
            for task in state.plan.get('tasks', []):
                print(f"  - {task.get('description')}")
        
        print(f"\nEvidence Gathered: {len(state.evidence)} items")
        for i, evidence in enumerate(state.evidence[:5], 1):  # Show first 5
            print(f"  {i}. [{evidence.get('source')}] {evidence.get('content')[:70]}...")
        
        print(f"\nAction Proposed:")
        if state.action_proposal:
            ap = state.action_proposal
            print(f"  - Action: {ap.get('action')} on {ap.get('service')}")
            print(f"  - Reason: {ap.get('reason')}")
            print(f"  - Expected: {ap.get('expected_outcome')}")
        
        print(f"\nVerification Decision:")
        if state.verification_decision:
            vd = state.verification_decision
            print(f"  - Approved: {vd.get('approved')}")
            print(f"  - Risk Level: {vd.get('risk_level')}")
            print(f"  - Blast Radius: {vd.get('blast_radius')}")
            print(f"  - Reason: {vd.get('reason')}")
        
        print(f"\nTool Results: {len(state.tool_results)} executed")
        for i, result_item in enumerate(state.tool_results, 1):
            print(f"  {i}. {result_item.get('tool_name')} - {result_item.get('status')}")
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print("\nkey takeaways:")
    print("✓ Multi-agent workflow executed deterministically")
    print("✓ Structured A2A message passing between agents")
    print("✓ Safety verification preventing unsafe actions")
    print("✓ Tool server abstraction for infrastructure access")
    print("✓ Complete execution trace for auditability")


if __name__ == "__main__":
    main()
