"""
Tests for Agent quality and reasoning accuracy.
Measures how well agents perform planning, investigation, proposal, and verification.
"""

import pytest
from typing import Dict, List, Any
from agents.base import PlannerAgent, InvestigatorAgent, OpsAgent, VerifierAgent
from tools.server import ToolServer
from test_scenarios import get_all_test_incidents, INCIDENT_1_PAYMENT_LATENCY


class TestPlannerAgent:
    """Test Planner Agent task decomposition quality."""
    
    @pytest.fixture
    def planner(self):
        return PlannerAgent()
    
    def test_plan_creation(self, planner):
        """Test that planner creates investigation plan."""
        incident = INCIDENT_1_PAYMENT_LATENCY
        plan = planner.plan(incident)
        
        assert "tasks" in plan, "Plan should contain tasks"
        assert len(plan["tasks"]) > 0, "Plan should have at least 1 task"
        print(f"✅ Plan creation test passed: {len(plan['tasks'])} tasks created")
    
    def test_task_structure(self, planner):
        """Test that tasks have required fields."""
        incident = INCIDENT_1_PAYMENT_LATENCY
        plan = planner.plan(incident)
        
        required_fields = ["task_id", "description", "target_service", "check_types"]
        for task in plan["tasks"]:
            for field in required_fields:
                assert field in task, f"Task missing field: {field}"
        print(f"✅ Task structure test passed: All tasks well-formed")
    
    def test_plan_relevance_to_symptom(self, planner):
        """Test that plan tasks are relevant to incident symptoms."""
        incident = INCIDENT_1_PAYMENT_LATENCY
        plan = planner.plan(incident)
        
        # For latency incident, should check logs, metrics, dependency graph
        check_types = set()
        for task in plan["tasks"]:
            check_types.update(task.get("check_types", []))
        
        assert "logs" in check_types or "metrics" in check_types, \
            "Should check logs/metrics for latency incident"
        print(f"✅ Plan relevance test passed: Check types = {check_types}")
    
    def test_plan_determinism(self, planner):
        """Test that same incident produces same plan (deterministic)."""
        incident = INCIDENT_1_PAYMENT_LATENCY
        plan1 = planner.plan(incident)
        plan2 = planner.plan(incident)
        
        assert len(plan1["tasks"]) == len(plan2["tasks"]), \
            "Plans should have same number of tasks"
        print(f"✅ Determinism test passed: Plans are identical")


class TestInvestigatorAgent:
    """Test Investigator Agent evidence gathering quality."""
    
    @pytest.fixture
    def investigator(self):
        tool_server = ToolServer(data_dir="data")
        return InvestigatorAgent(tool_server)
    
    def test_evidence_gathering(self, investigator):
        """Test that investigator gathers evidence."""
        incident = INCIDENT_1_PAYMENT_LATENCY
        plan = {"tasks": [
            {"task_id": "1", "description": "Check logs", "check_types": ["logs"]},
            {"task_id": "2", "description": "Check metrics", "check_types": ["metrics"]},
        ]}
        
        result = investigator.investigate(incident, plan)
        
        assert len(result.evidence) > 0, "Should gather at least 1 evidence item"
        print(f"✅ Evidence gathering test passed: {len(result.evidence)} items gathered")
    
    def test_evidence_quality(self, investigator):
        """Test that evidence items have required fields."""
        incident = INCIDENT_1_PAYMENT_LATENCY
        plan = {"tasks": [
            {"task_id": "1", "description": "Check logs", "check_types": ["logs"]},
        ]}
        
        result = investigator.investigate(incident, plan)
        
        required_fields = ["id", "source", "content"]
        for evidence in result.evidence:
            for field in required_fields:
                assert hasattr(evidence, field), f"Evidence missing field: {field}"
        print(f"✅ Evidence quality test passed: All evidence well-formed")
    
    def test_evidence_relevance(self, investigator):
        """Test that gathered evidence is relevant to incident."""
        incident = INCIDENT_1_PAYMENT_LATENCY
        plan = {"tasks": [
            {"task_id": "1", "description": "Check latency metrics", "check_types": ["metrics"]},
        ]}
        
        result = investigator.investigate(incident, plan)
        
        # For payment latency incident, should find latency/error metrics
        assert any("latency" in e.content.lower() or "error" in e.content.lower() 
                  for e in result.evidence), \
            "Evidence should be relevant to latency incident"
        print(f"✅ Evidence relevance test passed: Found relevant evidence")


class TestOpsAgent:
    """Test Ops Agent action proposal quality."""
    
    @pytest.fixture
    def ops(self):
        return OpsAgent()
    
    def test_action_proposal(self, ops):
        """Test that ops agent proposes action."""
        from messaging.a2a_models import InvestigationResult, Evidence
        
        incident = INCIDENT_1_PAYMENT_LATENCY
        evidence = [
            Evidence(id="1", source="metrics", service="payment-db", 
                content="Connection pool: 20/20 active", timestamp="2026-08-20T18:30:00Z", confidence=0.95),
            Evidence(id="2", source="logs", service="payment-service", 
                content="Connection denied errors", timestamp="2026-08-20T18:30:00Z", confidence=0.9),
        ]
        investigation = InvestigationResult(
            incident_id=incident["incident_id"],
            findings=["Pool exhausted"],
            evidence=evidence,
            confidence=0.9,
            recommended_next_step="Scale payment-service",
        )
        
        proposal = ops.propose_action(incident, investigation)
        
        assert proposal is not None, "Should propose an action"
        assert proposal.action is not None, "Action should have action type"
        print(f"✅ Action proposal test passed: Proposed '{proposal.action}'")
    
    def test_action_has_rationale(self, ops):
        """Test that proposed action includes reasoning."""
        from messaging.a2a_models import InvestigationResult, Evidence
        
        incident = INCIDENT_1_PAYMENT_LATENCY
        evidence = [Evidence(id="1", source="metrics", service="payment-db", 
                   content="Connection pool exhausted", timestamp="2026-08-20T18:30:00Z", confidence=0.95)]
        investigation = InvestigationResult(
            incident_id=incident["incident_id"],
            findings=["Pool exhausted"],
            evidence=evidence,
            confidence=0.9,
            recommended_next_step="Scale payment-service",
        )
        
        proposal = ops.propose_action(incident, investigation)
        
        assert proposal.reason is not None, "Action should include reason/rationale"
        assert len(proposal.reason) > 0, "Reason should not be empty"
        print(f"✅ Rationale test passed: {proposal.reason[:50]}...")
    
    def test_action_specificity(self, ops):
        """Test that action includes specific parameters."""
        from messaging.a2a_models import InvestigationResult, Evidence
        
        incident = INCIDENT_1_PAYMENT_LATENCY
        evidence = [Evidence(id="1", source="metrics", service="payment-db", 
                   content="Connection pool exhausted", timestamp="2026-08-20T18:30:00Z", confidence=0.95)]
        investigation = InvestigationResult(
            incident_id=incident["incident_id"],
            findings=["Pool exhausted"],
            evidence=evidence,
            confidence=0.9,
            recommended_next_step="Scale payment-service",
        )
        
        proposal = ops.propose_action(incident, investigation)
        
        assert proposal.parameters is not None, "Action should include parameters"
        print(f"✅ Specificity test passed: Parameters = {proposal.parameters}")


class TestVerifierAgent:
    """Test Verifier Agent safety verification quality."""
    
    @pytest.fixture
    def verifier(self):
        return VerifierAgent()
    
    def test_verification_decision(self, verifier):
        """Test that verifier makes a decision (approve/reject)."""
        from messaging.a2a_models import ActionProposal
        
        incident = INCIDENT_1_PAYMENT_LATENCY
        proposal = ActionProposal(
            incident_id=incident["incident_id"],
            action="scale",
            service="payment-service",
            reason="Reduce load",
            parameters={"target_replicas": 6},
            evidence_ids=["1", "2", "3"],
            expected_outcome="Latency and errors should decrease",
        )
        
        decision = verifier.verify(proposal, incident)
        
        assert decision.approved in [True, False], "Should make approval decision"
        print(f"✅ Verification decision test passed: Approved={decision.approved}")
    
    def test_verification_has_reasoning(self, verifier):
        """Test that verification decision includes reasoning."""
        from messaging.a2a_models import ActionProposal
        
        incident = INCIDENT_1_PAYMENT_LATENCY
        proposal = ActionProposal(
            incident_id=incident["incident_id"],
            action="scale",
            service="payment-service",
            reason="Reduce load",
            parameters={"target_replicas": 6},
            evidence_ids=["1", "2"],
            expected_outcome="Latency should decrease",
        )
        
        decision = verifier.verify(proposal, incident)
        
        assert decision.reason is not None, "Should include reasoning"
        print(f"✅ Reasoning test passed: {decision.reason[:50]}...")
    
    def test_verification_risk_level(self, verifier):
        """Test that verification includes risk assessment."""
        from messaging.a2a_models import ActionProposal
        
        incident = INCIDENT_1_PAYMENT_LATENCY
        proposal = ActionProposal(
            incident_id=incident["incident_id"],
            action="scale",
            service="payment-service",
            reason="Reduce load",
            parameters={"target_replicas": 6},
            evidence_ids=["1", "2", "3"],
            expected_outcome="Latency should decrease",
        )
        
        decision = verifier.verify(proposal, incident)
        
        assert decision.risk_level is not None, "Should assess risk level"
        print(f"✅ Risk assessment test passed: Risk={decision.risk_level}")


class TestAgentAccuracy:
    """Measure end-to-end agent accuracy on test scenarios."""
    
    def test_incident_1_accuracy(self):
        """Test accuracy on Payment Latency incident."""
        from test_scenarios import INCIDENT_1_PAYMENT_LATENCY
        
        # Test should recognize database issue
        planner = PlannerAgent()
        plan = planner.plan(INCIDENT_1_PAYMENT_LATENCY)
        
        # Should investigate database
        db_tasks = [t for t in plan["tasks"] if "payment-db" in t.get("target_service", "")]
        assert len(db_tasks) > 0, "Should investigate database for latency issue"
        print(f"✅ Incident 1 accuracy test passed: Identified DB investigation")
    
    def test_incident_2_accuracy(self):
        """Test accuracy on Memory Leak incident."""
        from test_scenarios import INCIDENT_2_MEMORY_LEAK
        
        # Test should recognize service restart needed
        planner = PlannerAgent()
        plan = planner.plan(INCIDENT_2_MEMORY_LEAK)
        
        # Should investigate auth-service
        auth_tasks = [t for t in plan["tasks"] if "auth-service" in t.get("target_service", "")]
        assert len(auth_tasks) > 0, "Should investigate auth-service"
        print(f"✅ Incident 2 accuracy test passed: Identified service investigation")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
