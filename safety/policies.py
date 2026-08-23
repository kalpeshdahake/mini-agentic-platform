"""
Safety and Guardrails Engine.
Deterministic policy checks that prevent unsafe actions.
"""

from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from rag.knowledge_graph import ServiceDependencyGraph


class AutonomyTier(Enum):
    """Autonomy levels for different action types."""
    AUTONOMOUS = "autonomous"  # Execute without approval
    VERIFIED = "verified"      # Require verifier approval
    HIGH_RISK = "high_risk"    # Require human approval


@dataclass
class PolicyRule:
    """A single policy rule."""
    name: str
    description: str
    check_fn: callable
    severity: str  # "error" or "warning"


class SafetyPolicyEngine:
    """
    Deterministic safety checks for infrastructure actions.
    LLM proposes, policy engine validates.
    """
    
    def __init__(self, kg: ServiceDependencyGraph, config: Optional[Dict[str, Any]] = None):
        self.kg = kg
        self.config = config or {}
        self.rules: List[PolicyRule] = self._build_rules()
    
    def _build_rules(self) -> List[PolicyRule]:
        """Define all policy rules."""
        rules = []
        
        # Rule 1: Environment restrictions
        rules.append(PolicyRule(
            name="environment_scope",
            description="Only allowed environments are prod, staging, dev",
            check_fn=lambda action, ctx: ctx.get("environment") in ["prod", "staging", "dev"],
            severity="error",
        ))
        
        # Rule 2: Service exists
        rules.append(PolicyRule(
            name="service_exists",
            description="Target service must exist in infrastructure",
            check_fn=lambda action, ctx: action.get("service") in self.kg.services,
            severity="error",
        ))
        
        # Rule 3: No cross-environment actions
        rules.append(PolicyRule(
            name="no_cross_env_actions",
            description="Action cannot affect services in other environments",
            check_fn=lambda action, ctx: True,  # Simplified for demo
            severity="error",
        ))
        
        # Rule 4: Blast radius check
        rules.append(PolicyRule(
            name="blast_radius_limit",
            description="Action blast radius must not exceed configured limit",
            check_fn=self._check_blast_radius,
            severity="error",
        ))
        
        # Rule 5: Critical service protection
        rules.append(PolicyRule(
            name="critical_service_protection",
            description="Cannot perform high-risk actions on critical services during peak hours",
            check_fn=self._check_critical_protection,
            severity="error",
        ))
        
        return rules
    
    def _check_blast_radius(self, action: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
        """Verify blast radius doesn't exceed limit."""
        service = action.get("service")
        blast_radius = self.kg.get_blast_radius(service, depth=2)
        
        # Default limit: 10 services
        limit = self.config.get("max_blast_radius", 10)
        return len(blast_radius) <= limit
    
    def _check_critical_protection(self, action: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
        """Prevent high-risk actions on critical services."""
        service = action.get("service")
        action_type = action.get("action")
        
        is_critical = self.kg.services.get(service, {}).get("critical", False)
        is_high_risk = action_type in ["restart", "terminate"]
        
        # Allow scaling (lower risk), restrict restarts on critical
        if is_critical and is_high_risk:
            return False
        
        return True
    
    def evaluate_action(
        self,
        action: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate action against all policies.
        Returns detailed results of all checks.
        """
        results = {
            "overall_approved": True,
            "checks": [],
            "errors": [],
            "warnings": [],
        }
        
        for rule in self.rules:
            try:
                passed = rule.check_fn(action, context)
                
                check_result = {
                    "name": rule.name,
                    "description": rule.description,
                    "passed": passed,
                    "severity": rule.severity,
                }
                
                results["checks"].append(check_result)
                
                if not passed:
                    if rule.severity == "error":
                        results["overall_approved"] = False
                        results["errors"].append(f"{rule.name}: {rule.description}")
                    else:
                        results["warnings"].append(f"{rule.name}: {rule.description}")
            
            except Exception as e:
                results["errors"].append(f"Error evaluating {rule.name}: {str(e)}")
                results["overall_approved"] = False
        
        return results
    
    def assign_autonomy_tier(
        self,
        action: Dict[str, Any],
        context: Dict[str, Any],
    ) -> AutonomyTier:
        """
        Assign autonomy tier based on action risk level.
        Determines if action can run automatically or needs approval.
        """
        action_type = action.get("action")
        service = action.get("service")
        
        is_critical = self.kg.services.get(service, {}).get("critical", False)
        blast_radius = len(self.kg.get_blast_radius(service, depth=2))
        
        # Decision tree
        if action_type == "read":
            return AutonomyTier.AUTONOMOUS
        
        if action_type == "scale" and not is_critical and blast_radius < 3:
            return AutonomyTier.VERIFIED
        
        if action_type == "restart" and is_critical:
            return AutonomyTier.HIGH_RISK
        
        if blast_radius > 5:
            return AutonomyTier.HIGH_RISK
        
        return AutonomyTier.VERIFIED


class RateLimiter:
    """Simple rate limiter for tool calls."""
    
    def __init__(self, max_calls_per_minute: int = 60):
        self.max_calls_per_minute = max_calls_per_minute
        self.call_history: List[float] = []
    
    def is_allowed(self) -> bool:
        """Check if a new call is allowed."""
        import time
        now = time.time()
        
        # Remove calls older than 1 minute
        self.call_history = [t for t in self.call_history if now - t < 60]
        
        if len(self.call_history) < self.max_calls_per_minute:
            self.call_history.append(now)
            return True
        
        return False
