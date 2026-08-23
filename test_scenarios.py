"""
Test scenarios for evaluation: Multiple incident types to test agent reasoning and RAG accuracy.
Each scenario has known correct diagnosis and remediation to measure accuracy.
"""

import json
from typing import Dict, List, Any
from datetime import datetime, timedelta


# Scenario 1: Database Connection Pool Exhaustion (ORIGINAL)
INCIDENT_1_PAYMENT_LATENCY = {
    "incident_id": "INC-2026-08-020",
    "timestamp": "2026-08-20T18:30:00Z",
    "title": "Payment API Latency Spike",
    "description": "Payment API latency has increased significantly over the last 30 minutes and error rates have started rising.",
    "environment": "prod",
    "affected_service": "payment-service",
    "severity": "high",
    "initial_symptoms": [
        "p95 latency increased from 200ms to 2000ms",
        "error rate increased from 0.01% to 2.5%",
        "5xx errors: GET /api/payment/status returning 503",
        "database connection pool saturation observed"
    ],
    "expected_diagnosis": "Payment-DB connection pool exhausted (20/20 active connections)",
    "expected_action": "scale payment-service",
    "expected_parameters": {"target_replicas": 6}
}

# Scenario 2: Memory Leak in Auth Service
INCIDENT_2_MEMORY_LEAK = {
    "incident_id": "INC-2026-08-021",
    "timestamp": "2026-08-20T19:15:00Z",
    "title": "Auth Service Memory Exhaustion",
    "description": "Auth service is consuming excessive memory and causing OOM killer to restart instances.",
    "environment": "prod",
    "affected_service": "auth-service",
    "severity": "critical",
    "initial_symptoms": [
        "Memory usage: 15.2GB / 16GB (95%)",
        "Process restarts every 10 minutes",
        "Heap dump shows StringBuilder objects in memory",
        "Auth token validation latency: 2500ms (normal: 15ms)"
    ],
    "expected_diagnosis": "Memory leak in token cache - StringBuilder accumulation in HashMap",
    "expected_action": "restart auth-service",
    "expected_parameters": {"force_restart": True}
}

# Scenario 3: Database Replication Lag
INCIDENT_3_REPLICATION_LAG = {
    "incident_id": "INC-2026-08-022",
    "timestamp": "2026-08-20T20:00:00Z",
    "title": "Database Replication Lag",
    "description": "Payment database replication lag is causing stale reads on reporting queries.",
    "environment": "prod",
    "affected_service": "payment-db",
    "severity": "medium",
    "initial_symptoms": [
        "Replication lag: 8500ms behind primary",
        "Reporting queries returning stale data (< 5 minutes old)",
        "Primary write throughput: 2500 ops/sec",
        "Replica CPU: 85%, network: 9.5Gbps/10Gbps"
    ],
    "expected_diagnosis": "Replica network saturated - high write throughput from primary",
    "expected_action": "scale payment-db replica",
    "expected_parameters": {"add_read_replicas": 2}
}

# Scenario 4: Cascade Failure (Fraud Service blocks Auth)
INCIDENT_4_CASCADE_FAILURE = {
    "incident_id": "INC-2026-08-023",
    "timestamp": "2026-08-20T21:30:00Z",
    "title": "Cascade Failure: Fraud Service Timeout",
    "description": "Fraud service timeout is blocking payment authentication, causing cascading failures across platform.",
    "environment": "prod",
    "affected_service": "payment-service",  # downstream impact
    "severity": "critical",
    "initial_symptoms": [
        "Payment API response: 503 Service Unavailable (50% of requests)",
        "Auth service timeout: 30s (waiting on fraud-service)",
        "Fraud service CPU: 99.8%, p99 latency: 32000ms",
        "Circuit breaker opened for fraud-service"
    ],
    "expected_diagnosis": "Fraud service CPU-bound - unoptimized fraud detection algorithm",
    "expected_action": "scale fraud-service",
    "expected_parameters": {"target_replicas": 8}
}

# Scenario 5: Disk Space Exhaustion (Logs filling disk)
INCIDENT_5_DISK_SPACE = {
    "incident_id": "INC-2026-08-024",
    "timestamp": "2026-08-20T22:45:00Z",
    "title": "Disk Space Critical",
    "description": "Payment service instances running out of disk space due to verbose logging.",
    "environment": "prod",
    "affected_service": "payment-service",
    "severity": "high",
    "initial_symptoms": [
        "Disk usage: 98.5GB / 99GB (99.5%)",
        "Log rotation failing - disk full",
        "New payment requests failing with 'No space left on device'",
        "/var/log/payment-service.log: 8.5GB (rotated 47 times in 24h)"
    ],
    "expected_diagnosis": "Log level set to DEBUG instead of INFO - verbose SQL logging enabled",
    "expected_action": "restart payment-service with correct log config",
    "expected_parameters": {"restart_with_config": "log_level=INFO"}
}

# Scenario 6: Network Configuration Issue
INCIDENT_6_NETWORK_PARTITION = {
    "incident_id": "INC-2026-08-025",
    "timestamp": "2026-08-21T01:00:00Z",
    "title": "Network Partition Between Services",
    "description": "Intermittent network connectivity between payment-service and notification-service.",
    "environment": "prod",
    "affected_service": "notification-service",
    "severity": "medium",
    "initial_symptoms": [
        "Packet loss: 15% to notification-service",
        "DNS resolution time: 3000ms (normal: 50ms)",
        "Network MTU mismatch detected: 1500 vs 1400",
        "Payment confirmations not sent (notification queue growing)"
    ],
    "expected_diagnosis": "Network configuration change - MTU/DNS zone misconfiguration",
    "expected_action": "restart notification-service with network config fix",
    "expected_parameters": {"reconfigure_network": True}
}

# Scenario 7: Resource Quota Exceeded
INCIDENT_7_QUOTA_EXCEEDED = {
    "incident_id": "INC-2026-08-026",
    "timestamp": "2026-08-21T03:15:00Z",
    "title": "CPU Quota Exceeded",
    "description": "Payment service CPU throttling due to exceeding pod quota limits.",
    "environment": "prod",
    "affected_service": "payment-service",
    "severity": "high",
    "initial_symptoms": [
        "Pod CPU throttle: 45% of requests throttled (cpu_throttle_time 45s/100s)",
        "CPU limit: 2.0, requested: 8.0",
        "Payment p99 latency: 5000ms during peak (normal: 250ms)",
        "Pod is CPU-bound, unable to process requests"
    ],
    "expected_diagnosis": "Kubernetes CPU quota mismatch - limit too low for actual demand",
    "expected_action": "scale payment-service horizontally",
    "expected_parameters": {"target_replicas": 10}
}

ALL_INCIDENTS = [
    INCIDENT_1_PAYMENT_LATENCY,
    INCIDENT_2_MEMORY_LEAK,
    INCIDENT_3_REPLICATION_LAG,
    INCIDENT_4_CASCADE_FAILURE,
    INCIDENT_5_DISK_SPACE,
    INCIDENT_6_NETWORK_PARTITION,
    INCIDENT_7_QUOTA_EXCEEDED,
]


def get_all_test_incidents() -> List[Dict[str, Any]]:
    """Return all test incidents."""
    return ALL_INCIDENTS


def get_incident_by_id(incident_id: str) -> Dict[str, Any]:
    """Get a specific incident by ID."""
    for incident in ALL_INCIDENTS:
        if incident["incident_id"] == incident_id:
            return incident
    raise ValueError(f"Incident {incident_id} not found")


def print_incident_summary():
    """Print summary of all test incidents."""
    print("\n" + "="*80)
    print("TEST INCIDENT SCENARIOS")
    print("="*80)
    for i, incident in enumerate(ALL_INCIDENTS, 1):
        print(f"\n{i}. {incident['title']}")
        print(f"   ID: {incident['incident_id']}")
        print(f"   Severity: {incident['severity']}")
        print(f"   Service: {incident['affected_service']}")
        print(f"   Expected Action: {incident['expected_action']}")
        print(f"   Diagnosis: {incident['expected_diagnosis']}")


if __name__ == "__main__":
    print_incident_summary()
