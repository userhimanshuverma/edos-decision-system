# EDOS Day 26: Local AI Explanation Layer (Ollama)

## Overview & Governing Principle

EDOS (Enterprise Decision Operating System) introduces its first AI integration in Day 26: an auditable, grounded natural-language explanation layer powered by a **local, open-weight language model** running in [Ollama](https://ollama.com).

Our core architectural principle is:

> **The system calculates. AI explains. Humans approve.**

The AI explanation layer interprets and translates deterministic system outputs for human operators. **It never:**
- Performs business arithmetic or calculates replenishment quantities.
- Computes or alters stockout-risk indicators, costs, or constraint outcomes.
- Selects, ranks, or changes recommended candidate actions.
- Auto-approves or rejects decisions.
- Fabricates citations, evidence identifiers, or calculation results.

---

## Architecture

```text
[Deterministic Decision Pipeline]
   │
   ├── Context Engine (Inventory, Demand, Supplier)
   ├── Recommendation Engine (LOD Selection, Evaluations)
   ├── Validation Engine (Physical/Business Hard Constraints)
   ├── Evidence & Provenance Services
   └── Replay & Scenario Repositories
         │
         ▼
[DecisionExplanationContextCollector]
   │  • Assembles grounded facts, metrics, and constraint results
   │  • Explicitly documents known assumptions and missing context
   │  • Guarantees historical decision/version linkage
         │
         ▼
[ExplanationService]
   │  • Controlled prompt treating business data as untrusted
   │  • Instructs model to explain existing deterministic recommendation
   │  • Enforces JSON schema structure
   │  • Performs post-generation grounding check on evidence IDs
         │
         ▼
[OllamaClient] ── HTTP (POST /api/chat) ──► [Local Ollama Runtime] (e.g. llama3.2:1b)
         │
         ▼
[POST /api/decisions/{decision_id}/explanation]
         │
         ▼
[Web UI / ExplanationPanel] (Reviewer reads explanation; confirms or rejects manually)
```

---

## Ollama Setup & Configuration

### 1. Prerequisites

1. Install Ollama from [ollama.com](https://ollama.com) (available for Windows, macOS, Linux).
2. Start the local daemon:
   ```bash
   ollama serve
   ```
3. Pull the default tested instruct model:
   ```bash
   ollama pull llama3.2:1b
   ```
   *(Any general-purpose instruct model can be configured via environment variables, e.g., `llama3.2`, `mistral`, `qwen2.5:3b`, etc.)*

### 2. Environment Configuration

Add the following environment variables to your `.env` or set them in your environment:

| Variable | Default Value | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL of local Ollama runtime |
| `OLLAMA_MODEL` | `llama3.2:1b` | Configurable model identifier |
| `OLLAMA_TIMEOUT_SECONDS` | `30.0` | HTTP request timeout for model inference |

The model can be replaced via configuration without touching any business or decision logic.

---

## API Specification

### Endpoint: `POST /api/decisions/{decision_id}/explanation`

- **Method:** `POST`
- **Path:** `/api/decisions/{decision_id}/explanation`
- **Request Body (Optional):**
  ```json
  {
    "version_id": "optional-version-id"
  }
  ```

### Response Schema: `DecisionExplanationResponse` (HTTP 200)

```json
{
  "decision_id": "DEC-0001",
  "decision_version_id": "VER-0001",
  "recommendation_summary": "Replenish 500 units from SUP-PRIMARY at $1,250.00.",
  "reasoning_summary": "Available stock (120 units) is below reorder point (300 units). Average daily demand is 25 units with 14 days supplier lead time, yielding 18 days of stockout exposure without replenishment.",
  "supporting_evidence": [
    "EVI-INV-001",
    "EVI-DMD-001",
    "CALC-REPLENISHMENT-001"
  ],
  "risks_and_constraints": [
    "Supplier lead time variability is 2.5 days.",
    "Warehouse capacity constraint passed with 85% utilization."
  ],
  "assumptions_and_missing_information": [
    "Assumes supplier unit cost remains stable over next 30 days.",
    "No historical replay record linked to this decision version."
  ],
  "review_considerations": [
    "Verify whether upcoming promotional cycle requires additional buffer."
  ],
  "limitations": [
    "Explanation is grounded solely in recorded decision context; cannot verify external supplier disruptions."
  ],
  "model_name": "llama3.2:1b",
  "generated_at": "2026-10-24T20:30:00Z"
}
```

### Error Handling & Graceful Degradation

If the local Ollama runtime is unavailable, the core EDOS decision engine continues operating normally without interruption. The API returns typed HTTP errors:

| Status Code | Reason | Meaning & Operator Action |
|---|---|---|
| `404 Not Found` | `DecisionNotFoundError` | The requested decision or version does not exist. |
| `422 Unprocessable` | `InsufficientContextError` | Decision lacks evaluated recommendations or context. |
| `503 Service Unavailable` | `OllamaConnectionError` / `OllamaModelNotFoundError` | Ollama daemon is offline or model is not pulled (`ollama serve`). |
| `502 Bad Gateway` | `UngroundedEvidenceError` / `OllamaResponseError` | LLM generated malformed output or cited ungrounded evidence IDs. |

---

## Grounding & Safety Guardrails

1. **Untrusted Data Isolation:** Prompt engineering instructs the LLM that notes, evidence strings, and supplier comments are untrusted text and must not be treated as executable instructions.
2. **Strict Identity Grounding:** Every cited `supporting_evidence` ID is cross-checked against the IDs provided in `DecisionExplanationContext`. If the model hallucinates an unknown ID, `UngroundedEvidenceError` is raised.
3. **No Numerical Mutation:** The prompt strictly forbids inventing numbers, recalculating quantities, or reporting differing recommendation parameters.
4. **Separation of Facts from Assumptions:** Unrecorded or incomplete historical facts (e.g., absence of replay data) are surfaced in `assumptions_and_missing_information`, never as established facts.
5. **No AI Sign-off:** The output explanation cannot change decision status to approved or rejected.

---

## Testing Without Ollama

All automated test suites in EDOS are fully decoupled from local daemons or external network calls. Tests use `httpx.MockTransport` to simulate Ollama responses, connection errors, timeouts, and edge cases.

### Running Backend Tests

```bash
cd apps/api
pytest tests/test_ollama_client.py tests/test_context_collector.py tests/test_explanation_service.py tests/test_explanation_api.py -v
```

Run entire backend suite:
```bash
pytest -q
```

### Running Frontend Tests

```bash
cd apps/web
node --test tests/explanation.test.mjs
```
