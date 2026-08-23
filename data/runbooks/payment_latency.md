# Payment Service High Latency

## Symptoms
- p95 latency > 2 seconds
- Database connection pool saturation
- payment-db CPU > 90%
- Increased error rates (500+ errors/minute)

## Root Cause Analysis
This usually indicates one of three issues:
1. Database connection pool exhaustion (most common)
2. Sudden traffic spike overwhelming the service
3. Cascading failure from dependent service

## Investigation Steps
1. Check payment-db connection pool status
2. Check payment-db CPU and memory utilization
3. Check recent payment-db query latency
4. Check auth-service and fraud-service latency
5. Review recent deployments in the last 1 hour

## Recommended Actions

### Option 1: Scale Payment Service (Lower Risk)
- Increase payment-service replicas from 3 to 6
- Expected: Distribute load, reduce per-instance latency
- Blast radius: payment-service only
- Rollback: Scale back to 3 replicas
- Time to effect: 2-3 minutes

### Option 2: Restart Payment DB (Higher Risk)
- Graceful restart of payment-db
- Expected: Clear connection pool, reset memory
- Blast radius: auth-service, fraud-service, payment-service
- Rollback: None (may require restore from backup)
- Time to effect: 30-60 seconds
- Preconditions: Only during low traffic hours, ensure backup is up-to-date

### Option 3: Reduce Load (Safest)
- Temporarily rate-limit payment-service clients
- Expected: Reduce database query throughput
- Blast radius: Potential impact on client services
- Rollback: Remove rate-limiting
- Time to effect: Immediate

## Safety Constraints
- Do NOT restart payment-db during peak traffic (17:00-20:00)
- Do NOT escalate to higher tiers without explicit approval
- Always check auth-service and fraud-service status before taking action
- Blast radius check: Ensure notification-service can handle degradation

## Verification
After action:
1. p95 latency should drop below 500ms within 2 minutes
2. Error rate should drop below 0.5%
3. Database connection pool should normalize to < 10 connections
4. All downstream services should return to normal operation

## Escalation
If neither option works:
1. Page on-call DBA
2. Prepare to roll back recent deployments
3. Consider disaster recovery procedures
