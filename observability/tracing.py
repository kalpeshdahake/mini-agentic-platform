"""
Observability and execution tracing.
Records complete workflow execution for post-mortem analysis and replay.
"""

import json
import sqlite3
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path


class ExecutionTracer:
    """
    Records detailed execution traces at agent and tool levels.
    Supports workflow replay and post-mortem analysis.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.traces: Dict[str, List[Dict[str, Any]]] = {}
        self.current_run_id: Optional[str] = None
    
    def start_run(self, run_id: str, incident_id: str) -> None:
        """Initialize a new run trace."""
        self.current_run_id = run_id
        self.traces[run_id] = []
        
        self._record_event(
            "workflow_started",
            {
                "run_id": run_id,
                "incident_id": incident_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    def record_agent_step(
        self,
        agent_name: str,
        step_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        decision: str,
        rejected_alternatives: List[str] = None,
        duration_ms: float = 0.0,
    ) -> None:
        """Record an agent processing step."""
        self._record_event(
            "agent_step",
            {
                "agent": agent_name,
                "step": step_name,
                "input": self._redact_sensitive(input_data),
                "output": self._redact_sensitive(output_data),
                "decision": decision,
                "rejected_alternatives": rejected_alternatives or [],
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    def record_tool_call(
        self,
        tool_name: str,
        tool_version: str,
        input_args: Dict[str, Any],
        output: Dict[str, Any],
        error: Optional[str] = None,
        duration_ms: float = 0.0,
        estimated_cost: Optional[float] = None,
    ) -> None:
        """Record a tool invocation."""
        self._record_event(
            "tool_call",
            {
                "tool_name": tool_name,
                "tool_version": tool_version,
                "input": self._redact_sensitive(input_args),
                "output": self._redact_sensitive(output),
                "error": error,
                "duration_ms": duration_ms,
                "estimated_cost": estimated_cost,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    def record_policy_check(
        self,
        check_name: str,
        passed: bool,
        details: Dict[str, Any],
    ) -> None:
        """Record a policy or safety check."""
        self._record_event(
            "policy_check",
            {
                "check_name": check_name,
                "passed": passed,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    def record_state_transition(
        self,
        from_state: str,
        to_state: str,
        reason: str,
    ) -> None:
        """Record workflow state transition."""
        self._record_event(
            "state_transition",
            {
                "from": from_state,
                "to": to_state,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    def record_error(self, error_message: str, context: Dict[str, Any] = None) -> None:
        """Record an error or exception."""
        self._record_event(
            "error",
            {
                "message": error_message,
                "context": context or {},
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    def _record_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Record a generic event."""
        if self.current_run_id:
            event = {
                "type": event_type,
                **data,
            }
            self.traces[self.current_run_id].append(event)
    
    def _redact_sensitive(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from data."""
        # In production, redact tokens, passwords, PII, etc.
        # For this demo, just limit data size
        if not isinstance(data, dict):
            return data
        
        redacted = {}
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 1000:
                redacted[key] = value[:1000] + "...[TRUNCATED]"
            else:
                redacted[key] = value
        
        return redacted
    
    def get_run_trace(self, run_id: str) -> List[Dict[str, Any]]:
        """Retrieve complete trace for a run."""
        return self.traces.get(run_id, [])
    
    def export_trace(self, run_id: str, filepath: Optional[str] = None) -> str:
        """Export trace to JSON file."""
        trace = self.get_run_trace(run_id)
        
        if not filepath:
            filepath = str(self.data_dir / f"trace_{run_id}.json")
        
        with open(filepath, 'w') as f:
            json.dump(trace, f, indent=2)
        
        return filepath


class WorkflowStateStore:
    """
    Persistent storage for workflow state using SQLite.
    Enables replay and recovery.
    """
    
    def __init__(self, db_path: str = "workflow_state.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Workflow runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_runs (
                run_id TEXT PRIMARY KEY,
                incident_id TEXT,
                current_state TEXT,
                created_at TEXT,
                updated_at TEXT,
                state_data TEXT
            )
        """)
        
        # State history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                from_state TEXT,
                to_state TEXT,
                timestamp TEXT,
                FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_workflow_state(
        self,
        run_id: str,
        incident_id: str,
        current_state: str,
        state_data: Dict[str, Any],
    ) -> None:
        """Save or update workflow state."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        state_json = json.dumps(state_data)
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO workflow_runs
            (run_id, incident_id, current_state, created_at, updated_at, state_data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (run_id, incident_id, current_state, now, now, state_json))
        
        conn.commit()
        conn.close()
    
    def record_state_transition(
        self,
        run_id: str,
        from_state: str,
        to_state: str,
    ) -> None:
        """Record state transition in history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT INTO state_history (run_id, from_state, to_state, timestamp)
            VALUES (?, ?, ?, ?)
        """, (run_id, from_state, to_state, now))
        
        conn.commit()
        conn.close()
    
    def get_workflow_state(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve workflow state."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT current_state, state_data FROM workflow_runs WHERE run_id = ?",
            (run_id,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                "current_state": result[0],
                "state_data": json.loads(result[1]),
            }
        
        return None
    
    def get_state_history(self, run_id: str) -> List[Dict[str, Any]]:
        """Get state transition history for a run."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT from_state, to_state, timestamp
            FROM state_history
            WHERE run_id = ?
            ORDER BY timestamp ASC
        """, (run_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "from_state": row[0],
                "to_state": row[1],
                "timestamp": row[2],
            }
            for row in rows
        ]
