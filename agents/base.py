"""
Agent implementations with deterministic logic.
LLM reasoning will be added in production, but structure remains the same.
"""

from typing import Dict, List, Any, Optional
from messaging.a2a_models import (
    Evidence,
    InvestigationRequest,
    InvestigationResult,
    ActionProposal,
    VerificationDecision,
    RiskLevel,
    PolicyCheck,
)
from tools.server import ToolServer
import uuid


class PlannerAgent:
    """
    Decomposes the incident into investigation tasks.
    No LLM needed for this mock implementation.
    """
    
    def __init__(self, name: str = "PlannerAgent", llm_client: Any = None):
        self.name = name
        self.llm_client = llm_client
    
    def plan(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decompose incident into investigation tasks.
        Returns structured plan that Investigator will execute.
        """
        service = incident.get("affected_service", "unknown")
        symptoms = incident.get("initial_symptoms", [])
        
        tasks = []
        
        # Task 1: Check database health
        tasks.append({
            "task_id": str(uuid.uuid4()),
            "description": "Check payment-db connection pool and resource utilization",
            "target_service": "payment-db",
            "check_types": ["logs", "metrics", "dependency_graph"],
        })
        
        # Task 2: Check dependent services
        tasks.append({
            "task_id": str(uuid.uuid4()),
            "description": "Check auth-service and fraud-service latency",
            "target_service": "auth-service",
            "check_types": ["logs", "metrics"],
        })
        
        # Task 3: Retrieve relevant runbooks
        tasks.append({
            "task_id": str(uuid.uuid4()),
            "description": "Retrieve payment latency troubleshooting runbook",
            "target_service": "payment-service",
            "check_types": ["runbooks"],
        })
        
        # Task 4: Check primary service
        tasks.append({
            "task_id": str(uuid.uuid4()),
            "description": "Check payment-service logs and metrics",
            "target_service": "payment-service",
            "check_types": ["logs", "metrics"],
        })
        
        plan = {
            "plan_id": str(uuid.uuid4()),
            "incident_id": incident.get("incident_id"),
            "description": "Systematically investigate payment service latency incident",
            "tasks": tasks,
            "investigation_priority": ["database_health", "dependency_health", "error_analysis"],
        }

        if self.llm_client and self.llm_client.enabled:
            try:
                plan["llm_reasoning"] = self.llm_client.generate(
                    f"Suggest investigation priorities for this incident. Return concise text only.\n{incident}"
                )
            except Exception as error:
                print(f"[{self.name}] Local LLM unavailable: {error}")
        
        print(f"[{self.name}] Planned {len(tasks)} investigation tasks")
        return plan


class InvestigatorAgent:
    """
    Retrieves evidence using logs, metrics, and knowledge graph.
    Uses tools from ToolServer to access infrastructure data.
    """
    
    def __init__(self, tool_server: ToolServer, name: str = "InvestigatorAgent"):
        self.tool_server = tool_server
        self.name = name
    
    def investigate(
        self,
        incident: Dict[str, Any],
        plan: Dict[str, Any],
    ) -> InvestigationResult:
        """
        Execute investigation tasks and gather evidence.
        """
        incident_id = incident.get("incident_id")
        environment = incident.get("environment", "prod")
        service = incident.get("affected_service", "payment-service")
        
        evidence_list: List[Evidence] = []
        
        # Task 1: Check payment-db logs
        try:
            from tools.schemas import GetLogsRequest
            logs_response = self.tool_server.get_logs(GetLogsRequest(
                service="payment-db",
                environment=environment,
                timeframe="30m",
                limit=10,
            ))
            
            # Extract key findings
            if logs_response.logs:
                for log in logs_response.logs:
                    if "error" in log.message.lower() or "fail" in log.message.lower():
                        evidence_list.append(Evidence(
                            id=str(uuid.uuid4()),
                            source="logs",
                            service="payment-db",
                            content=log.message,
                            timestamp=log.timestamp,
                            confidence=0.95,
                        ))
        except Exception as e:
            print(f"[{self.name}] Error retrieving logs: {e}")
        
        # Task 2: Check payment-service metrics
        try:
            from tools.schemas import GetMetricsRequest
            metrics_response = self.tool_server.get_metrics(GetMetricsRequest(
                service="payment-service",
                environment=environment,
                metric_names=["p95_latency_ms", "error_rate_percent"],
            ))
            
            for metric in metrics_response.metrics:
                if metric.metric_name == "p95_latency_ms" and metric.value > 1000:
                    evidence_list.append(Evidence(
                        id=str(uuid.uuid4()),
                        source="metrics",
                        service="payment-service",
                        content=f"High p95 latency detected: {metric.value}ms at {metric.timestamp}",
                        timestamp=metric.timestamp,
                        confidence=0.99,
                    ))
                elif metric.metric_name == "error_rate_percent" and metric.value > 1.0:
                    evidence_list.append(Evidence(
                        id=str(uuid.uuid4()),
                        source="metrics",
                        service="payment-service",
                        content=f"Elevated error rate: {metric.value}% at {metric.timestamp}",
                        timestamp=metric.timestamp,
                        confidence=0.99,
                    ))
        except Exception as e:
            print(f"[{self.name}] Error retrieving metrics: {e}")
        
        # Task 3: Check dependency graph
        try:
            from tools.schemas import GetDependencyGraphRequest
            graph_response = self.tool_server.get_dependency_graph(
                GetDependencyGraphRequest(environment=environment)
            )
            
            evidence_list.append(Evidence(
                id=str(uuid.uuid4()),
                source="dependency_graph",
                service="payment-service",
                content=f"Dependency graph retrieved: {len(graph_response.services)} services, {len(graph_response.edges)} dependencies",
                timestamp="2026-08-20T18:40:00Z",
                confidence=1.0,
            ))
        except Exception as e:
            print(f"[{self.name}] Error retrieving dependency graph: {e}")
        
        # Root cause analysis
        findings = [
            "Database connection pool is exhausted (20/20 active connections)",
            "Payment-DB CPU utilization at 94%, memory at 85%",
            "Payment-service p95 latency increased from 200ms to 2800ms",
            "Error rate increased from 0.01% to 5.2%",
            "Auth-service and fraud-service showing latency increases (depending on payment-db)",
            "Likely root cause: Database connection pool exhaustion due to slow queries or stale connections",
        ]
        
        print(f"[{self.name}] Investigation complete: {len(evidence_list)} evidence items gathered")
        
        return InvestigationResult(
            incident_id=incident_id,
            findings=findings,
            evidence=evidence_list,
            confidence=0.92,
            recommended_next_step="Propose scaling payment-service or restarting payment-db per runbook",
        )


class OpsAgent:
    """
    Proposes concrete remediation actions.
    Uses evidence and knowledge to recommend safe actions.
    """
    
    def __init__(self, name: str = "OpsAgent", llm_client: Any = None):
        self.name = name
        self.llm_client = llm_client
    
    def propose_action(
        self,
        incident: Dict[str, Any],
        investigation: InvestigationResult,
    ) -> ActionProposal:
        """
        Propose a remediation action based on investigation.
        """
        # Choose action based on findings
        # For database saturation: Scale payment-service first (lower risk)
        
        action = ActionProposal(
            incident_id=incident.get("incident_id"),
            action="scale",
            service="payment-service",
            parameters={
                "target_replicas": 6,
                "current_replicas": 3,
            },
            reason="Scale payment-service from 3 to 6 replicas to reduce load on database and distribute query processing",
            evidence_ids=[e.id for e in investigation.evidence[:3]],  # Cite top 3 evidence pieces
            expected_outcome="P95 latency should drop below 500ms within 2 minutes, error rate should normalize",
        )

        if self.llm_client and self.llm_client.enabled:
            try:
                print(f"[{self.name}] Local LLM reasoning enabled ({self.llm_client.model})")
                self.llm_client.generate(
                    f"Explain this proposed remediation briefly; do not change the action.\n{action.model_dump()}"
                )
            except Exception as error:
                print(f"[{self.name}] Local LLM unavailable: {error}")
        
        print(f"[{self.name}] Proposed action: {action.action} {action.service}")
        return action


class VerifierAgent:
    """
    Validates actions against safety constraints.
    Deterministic policy checks, no LLM needed.
    """
    
    def __init__(self, name: str = "VerifierAgent"):
        self.name = name
    
    def verify(
        self,
        action_proposal: ActionProposal,
        incident: Dict[str, Any],
        dependency_graph: Optional[Dict[str, Any]] = None,
    ) -> VerificationDecision:
        """
        Verify action safety before execution.
        Deterministic policy checks prevent unsafe operations.
        """
        
        policy_checks = []
        
        # Check 1: Environment scope
        env = incident.get("environment", "prod")
        policy_checks.append(PolicyCheck(
            check_name="environment_scope",
            passed=env in ["prod", "staging", "dev"],
            reason=f"Environment {env} is allowed" if env in ["prod", "staging", "dev"] else f"Unknown environment {env}",
        ))
        
        # Check 2: Action allowed for service
        policy_checks.append(PolicyCheck(
            check_name="action_allowed_for_service",
            passed=True,  # Scaling is always allowed
            reason="Scaling action is permitted for stateless services",
        ))
        
        # Check 3: Time-based check (simplified)
        # In production: Check traffic patterns
        policy_checks.append(PolicyCheck(
            check_name="safe_time_window",
            passed=True,  # Simplified mock
            reason="Current time window is acceptable for medium-risk actions",
        ))
        
        # Check 4: Blast radius
        blast_radius = ["payment-service"]  # Only affects payment-service
        policy_checks.append(PolicyCheck(
            check_name="blast_radius",
            passed=len(blast_radius) <= 5,
            reason=f"Blast radius includes {len(blast_radius)} services (limit: 5)",
        ))
        
        # Check 5: Evidence requirement
        policy_checks.append(PolicyCheck(
            check_name="sufficient_evidence",
            passed=len(action_proposal.evidence_ids) > 0,
            reason=f"Action supported by {len(action_proposal.evidence_ids)} evidence items",
        ))
        
        # All checks must pass
        all_passed = all(check.passed for check in policy_checks)
        
        decision = VerificationDecision(
            incident_id=action_proposal.incident_id,
            approved=all_passed,
            risk_level=RiskLevel.MEDIUM if all_passed else RiskLevel.HIGH,
            blast_radius=blast_radius,
            policy_checks=policy_checks,
            reason="All safety checks passed" if all_passed else "Some safety checks failed",
            safer_alternative=None,
        )
        
        print(f"[{self.name}] Verification result: {'APPROVED' if all_passed else 'REJECTED'}")
        return decision
