# Mini Agentic AI Platform

A local multi-agent platform for production incident investigation and simulated remediation. The project demonstrates how specialized agents can collaborate through structured messages, retrieve evidence from operational data, propose a remediation, pass a deterministic safety gate, execute a controlled tool, and verify the result.

This is an interview/demo prototype. The infrastructure action is simulated and does not change a real production system.

## What This Project Solves

The sample use case is a payment API latency incident:

```text
Incident detected
    -> Planner creates investigation tasks
    -> Investigator gathers logs, metrics, runbook, and topology evidence
    -> Ops agent proposes a remediation action
    -> Verifier checks risk and policy deterministically
    -> Approved action is executed through the tool layer
    -> Post-action verification runs
    -> Incident is resolved or failed safely
```

The default scenario identifies high latency, rising errors, and database connection pool pressure, then proposes scaling `payment-service` from 3 to 6 replicas.

## Current Technology Stack

| Area | Technology | Role |
| --- | --- | --- |
| Language | Python 3.11 | Application and tests |
| Agent LLM | Ollama, default `mistral:latest` | Optional local reasoning for Planner and Ops |
| Embeddings | `all-MiniLM-L6-v2` via sentence-transformers | Semantic document embeddings |
| Vector database | FAISS `IndexFlatIP` | In-memory local vector similarity search |
| Keyword search | BM25 | Lexical evidence retrieval |
| Validation | Pydantic | A2A message and tool contracts |
| Orchestration | Explicit Python state machine | Valid workflow transitions |
| Persistence | JSON reports and optional SQLite classes | Run output, audit, replay support |
| Testing | pytest | Unit, integration, RAG, and safety tests |

The LLM, embeddings, and FAISS components are local. No cloud API key is required. The application keeps a deterministic fallback so tests and demos can run when Ollama or the downloaded embedding model is unavailable.

## Prerequisites

- Windows, macOS, or Linux
- Python 3.11 recommended
- At least 8 GB RAM: use a smaller Ollama model if `mistral` is slow
- Ollama installed for real local LLM reasoning
- Git, if cloning this repository

## Installation

From the project directory:

### Windows PowerShell

```powershell
cd d:\Kalpesh\Mapgenesis_Mini_Agentic_Task\mini-agentic-platform
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### New virtual environment, if needed

```powershell
cd d:\Kalpesh\Mapgenesis_Mini_Agentic_Task
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r mini-agentic-platform\requirements.txt
```

The first RAG run downloads `all-MiniLM-L6-v2` from Hugging Face and caches it in the user model cache. FAISS is configured with NumPy below version 2 for compatibility.

## Enable the Local Open-Source LLM

Ollama is a separate desktop application. The Python package in `requirements.txt` is only the client dependency; the Ollama application supplies the local model server.

Install a model once:

```powershell
ollama pull mistral
```

Start the local Ollama service in a separate terminal:

```powershell
ollama serve
```

Verify the model:

```powershell
ollama list
```

You should see `mistral:latest`. You can also test it interactively:

```powershell
ollama run mistral
```

Keep the Ollama service running, but run the project demo from another terminal.

The application connects to `http://localhost:11434`. `llm_client.py` calls the local `/api/tags` and `/api/generate` endpoints. If the server or model is unavailable, the application reports fallback mode and continues with deterministic agent logic.

## Run the Demo

With Ollama running for real LLM reasoning:

```powershell
cd d:\Kalpesh\Mapgenesis_Mini_Agentic_Task\mini-agentic-platform
..\.venv\Scripts\python.exe run_demo.py
```

Expected initialization output:

```text
[INIT] Local LLM: mistral (available)
```

The complete workflow prints these stages:

1. `PLANNING`: Planner creates four investigation tasks.
2. `INVESTIGATING`: Investigator reads operational data and gathers evidence.
3. `ACTION PROPOSAL`: Ops agent proposes a structured scale action.
4. `SAFETY CHECK`: Verifier evaluates deterministic policies.
5. `EXECUTING`: The simulated scale tool runs after approval.
6. `VERIFYING`: The result is checked.
7. `RESOLVED`: The workflow closes successfully.

A successful run ends with:

```text
Final State: WorkflowState.RESOLVED
Tool executed: success
Errors: 0 errors detected
```

The project never changes a real service. `simulate_scale` and `simulate_restart` return synthetic results.

## Input Data

The demo starts with `data/incident.json`:

```json
{
  "incident_id": "INC-2026-08-020",
  "description": "Payment API latency has increased significantly...",
  "environment": "prod",
  "affected_service": "payment-service",
  "severity": "high"
}
```

Supporting input data is stored under `data/`:

```text
data/
├── incident.json                         Incident ticket
├── logs/payment_service.log              Synthetic service and database logs
├── metrics/metrics.json                  Latency, errors, CPU, and memory data
├── runbooks/payment_latency.md           Troubleshooting and remediation guidance
└── infrastructure/services.json          Services, ownership, replicas, dependencies
```

`test_scenarios.py` contains seven additional synthetic incident tickets used by integration and accuracy tests. They cover payment latency, memory exhaustion, replication lag, cascade failure, disk exhaustion, network configuration, and CPU quota issues.

## Architecture

### Agent layer

- `PlannerAgent` decomposes an incident into explicit investigation tasks. It can request supplementary reasoning from Ollama.
- `InvestigatorAgent` uses read-only tools and builds typed `Evidence` objects with source, timestamp, and confidence.
- `OpsAgent` converts findings into an `ActionProposal` containing action, service, parameters, reason, expected outcome, and evidence IDs. It can request supplementary reasoning from Ollama.
- `VerifierAgent` creates a typed `VerificationDecision`. Its authorization logic is deterministic and does not depend on LLM output.

### Orchestration layer

`orchestration/state.py` defines the workflow states and valid transitions:

```text
RECEIVED -> PLANNING -> INVESTIGATING -> ACTION_PROPOSED -> SAFETY_CHECK
SAFETY_CHECK -> APPROVED -> EXECUTING -> VERIFYING -> RESOLVED
SAFETY_CHECK -> REJECTED
Any active state -> FAILED when an unrecoverable error occurs
```

`orchestration/graph.py` runs the sequence, validates transitions, stores intermediate state, handles rejected actions, and records failures.

### Message contracts

`messaging/a2a_models.py` contains Pydantic contracts such as `InvestigationRequest`, `InvestigationResult`, `ActionProposal`, `VerificationDecision`, `Evidence`, and `ExecutionTrace`. This prevents agents from exchanging ambiguous free-form structures.

### Retrieval and knowledge

`rag/hybrid.py` loads runbooks and infrastructure documents, then combines BM25 lexical scores with semantic embedding scores. The preferred embedder is `SentenceTransformerEmbedder` using `all-MiniLM-L6-v2`; `EmbeddingSimulator` is the deterministic fallback.

`rag/vector_store.py` provides the local FAISS vector store. It uses normalized embeddings and inner-product similarity. The index is built in memory when `HybridRAGPipeline` loads documents; it is not currently persisted as a separate index file.

`rag/knowledge_graph.py` loads service dependencies and calculates blast radius by graph traversal. This keeps impact analysis grounded in topology instead of asking an LLM to guess.

### Tools

`tools/schemas.py` defines versioned Pydantic input and output contracts. `tools/server.py` is the only infrastructure access layer and currently provides:

- `get_logs`
- `get_metrics`
- `get_dependency_graph`
- `simulate_restart`
- `simulate_scale`

All calls are environment-scoped. Agents do not call infrastructure SDKs directly.

### Safety

`safety/policies.py` contains deterministic checks for environment scope, service/action rules, time window, blast radius, evidence, critical services, autonomy tiers, and rate limiting. The core principle is:

```text
LLM proposes -> schemas validate -> policies authorize -> tool executes -> result is recorded
```

Even if an LLM produces an unsafe recommendation, it cannot skip the verifier, state machine, or tool boundary. `AUTONOMOUS`, `VERIFIED`, and `HIGH_RISK` represent increasing approval requirements.

## Where Outputs Are Stored

### Demo report files

Every successful or failed `run_demo.py` execution creates:

```text
output/run_<run-id>.json
```

The report includes:

- Original incident input
- Run ID and workflow summary
- Ollama provider, model, availability, and fallback status
- Embedding model and vector database metadata
- Plan and investigation evidence
- Proposed action and rationale
- Safety decision, risk level, blast radius, and policy result
- Tool execution result
- Final workflow state, timestamps, and errors

The generated report is the main persistent output for review or GitHub demonstration. The `output/` directory is retained with `.gitkeep`; generated run reports can be excluded from commits if desired.

### Console output

The terminal displays progress, agent decisions, evidence, safety status, and the final summary in real time. Pytest results are also displayed in the terminal and are not automatically saved to a file.

### Tracing and SQLite support

`observability/tracing.py` provides reusable `ExecutionTracer` and `WorkflowStateStore` classes:

- `ExecutionTracer` stores workflow events in memory and can export a JSON trace.
- `WorkflowStateStore` can persist workflow snapshots and state history to `workflow_state.db`.

The current `run_demo.py` writes the simpler complete report under `output/`; it does not automatically create a SQLite database unless the state-store class is used by an integration.

## Testing and Evaluation

Run all tests:

```powershell
cd d:\Kalpesh\Mapgenesis_Mini_Agentic_Task\mini-agentic-platform
..\.venv\Scripts\python.exe -m pytest tests -v -s
```

The test suite covers:

- **RAG:** BM25 retrieval, embeddings, FAISS-compatible ranking, metadata filtering, and evidence relevance.
- **Agents:** Plan creation, task structure, evidence gathering, action proposals, rationale, and risk decisions.
- **Integration:** Multiple incident scenarios, end-to-end workflow inputs, action accuracy, evidence quality, safety decisions, and latency.
- **Safety invariants:** Environment isolation, evidence requirements, blast-radius checks, and critical-service protection.

The seven test tickets are reference scenarios with expected diagnoses/actions. The tests calculate action accuracy and evidence-quality scores and print those values. These are scenario-based metrics, not a claim of production accuracy or model benchmark performance.

A successful test run currently reports:

```text
42 passed
```

## Repository Structure

```text
mini-agentic-platform/
├── agents/
│   └── base.py                 Four agent implementations
├── data/
│   ├── incident.json           Default incident ticket
│   ├── logs/                   Synthetic logs
│   ├── metrics/                Synthetic metrics
│   ├── runbooks/               Retrieval source document
│   └── infrastructure/         Service topology
├── evaluation/
│   └── eval_runner.py          Trajectory, invariant, and contract evaluation
├── messaging/
│   └── a2a_models.py           Pydantic A2A contracts
├── observability/
│   └── tracing.py              JSON tracing and SQLite state support
├── orchestration/
│   ├── graph.py                Workflow execution
│   └── state.py                State definitions and transitions
├── rag/
│   ├── hybrid.py               BM25 plus semantic retrieval
│   ├── knowledge_graph.py      Dependency graph and blast radius
│   └── vector_store.py         FAISS local vector store
├── safety/
│   └── policies.py             Deterministic policy engine
├── tests/
│   ├── test_agents.py          Agent behavior tests
│   ├── test_integration.py     Scenario and accuracy tests
│   ├── test_rag.py             Retrieval tests
│   └── test_safety.py          Safety invariant tests
├── tools/
│   ├── schemas.py              Tool contracts
│   └── server.py               Simulated tool server
├── output/                     Generated JSON run reports
├── llm_client.py               Ollama local API client
├── requirements.txt            Python dependencies
├── run_demo.py                 End-to-end demo entry point
└── test_scenarios.py           Seven evaluation incident tickets
```

## Limitations and Production Improvements

This implementation is intentionally local and safe for a hands-on exercise:

- Infrastructure operations are simulated JSON responses, not AWS/Kubernetes changes.
- The FAISS index is in memory and is rebuilt when the RAG pipeline starts.
- The local LLM is optional supplementary reasoning; core plan/action behavior remains deterministic for reliable demos.
- The sample data is synthetic and small; retrieval metrics are not production benchmarks.
- The demo is command-line based and single-machine.
- Human approval, rollback, IAM, secrets management, multi-tenancy, distributed tracing, durable queues, and real monitoring are not implemented.

A production version would add real infrastructure adapters, human approval for high-risk actions, durable vector storage, prompt/version management, larger regression datasets, rollback plans, authentication, authorization, and distributed observability.

## Troubleshooting

### `Local LLM: mistral (fallback mode)`

Start Ollama and ensure the model exists:

```powershell
ollama serve
ollama list
ollama pull mistral
```

### `404` from `/api/generate`

The Ollama server is reachable but the requested model is unavailable or the server version is not serving the expected endpoint. Confirm `ollama list` contains `mistral:latest`, then restart Ollama.

### Demo pauses at `STEP 1`

The first Mistral request can be slow on an 8 GB CPU-only laptop because the model must load into memory. Keep the Ollama terminal open and wait for the first request to finish.

### Embedding model download or import error

Run the requirements installation again. The project pins `numpy<2` and uses `sentence-transformers>=3,<4` for compatibility with FAISS and Hugging Face Hub.

### Run the deterministic fallback intentionally

Stop Ollama or use a machine without the Ollama service. The demo will continue with deterministic logic, which is useful for repeatable tests.

