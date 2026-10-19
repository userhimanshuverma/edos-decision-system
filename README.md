# EDOS

**Enterprise Decision Operating System**

## What is EDOS?

EDOS is an explainable, reproducible operational decision system. It empowers organizations and operators to:

* **Understand a situation**: Ingest operational signals and establish immediate situational awareness.
* **Evaluate possible actions**: Screen and validate candidate actions against business policies and operational constraints.
* **Compare scenarios**: Simulate impact projections and counterfactual scenarios before taking action.
* **Understand evidence and calculations**: Inspect complete mathematical calculations, citations, and underlying data points.
* **Review risks**: Surface operational trade-offs, potential side effects, and risk exposures.
* **Receive an AI-generated explanation**: Read clear, concise natural-language narratives describing why an action was recommended.
* **Approve, reject, or request review**: Provide governed human-in-the-loop sign-off on decisions before execution.

## V1 Philosophy

> EDOS is not a collection of dashboards or an AI chatbot. V1 focuses on one excellent decision workflow.

## Core Principle

> **The system calculates. AI explains. Humans approve.**

The AI must not be the source of truth for numerical decisions. All evaluations, projections, and candidate scoring originate from deterministic system logic.

## Architecture

Target V1 Architecture:

```text
Web UI
  ↓
FastAPI
  ↓
Decision Runtime
  ↓
Context / Decision / Scenario Engines
  ↓
Validation
  ↓
Decision Result
  ↓
Evidence / Risk / Provenance
  ↓
AI Explanation
  ↓
Human Approval
```

*(Note: The diagram above depicts the target V1 architecture. Day 1 focuses exclusively on establishing the system foundation).*

## Current Status

**Day 21: Hard-Constraint Validation Engine (Trust the Decision Phase Initiated)**

The repository currently establishes:
- Standard repository layout and conventions
- Python + FastAPI backend foundation with `/health` validation
- Next.js + React + TypeScript web foundation with enterprise light design system
- ShopFlow operational domain models (`Product`, `Supplier`, `Warehouse`, `Inventory`, `Demand`) with synthetic generator
- Deterministic Context Engine with unified situational status classification
- Business Decision identity and lifecycle state management (`DecisionStatus`: DRAFT → CONTEXTUALIZING → CONSTRUCTING → VALIDATING → EVALUATING → READY)
- Decision Event History and audit trail (`DecisionEvent`, `DecisionEventType`)
- Historical Decision Version snapshots (`DecisionVersion`, `DecisionSnapshot`)
- Decision Graph & Provenance Foundation (`DecisionGraph`, `GraphNode`, `GraphEdge`, `GraphNodeType`, `GraphRelationshipType`)
- Candidate Action Model representing operational alternatives (`DO_NOTHING`, `PLACE_ORDER`, `SWITCH_SUPPLIER`) with strict parameter typing and supplier eligibility validation
- Deterministic Replenishment Quantity Calculation Logic under explicit policies (`REORDER_POINT_DEFICIT`, `LEAD_TIME_DEMAND`, `TARGET_STOCK`) with auditable mathematical breakdown
- Decoupled Candidate Action integration generating explicit `PLACE_ORDER` actions from calculated quantities with complete provenance metadata
- Deterministic Stockout-Risk Calculation Engine (`StockoutRiskService`, `calculate_stockout_risk`) evaluating lead-time demand exposure, coverage runway buffer, and stockout deficit
- Deterministic Action Evaluation Engine (`ActionEvaluationService`, `evaluate_candidate_action`) assessing candidate actions individually across stockout exposure, replenishment impact, supplier impact, and defensible cost without arbitrary composite scoring
- Deterministic Recommendation Engine (`RecommendationService`, `select_deterministic_recommendation`) ranking candidate actions via Lexicographic Operational Dominance (LOD) and selecting optimal recommendations with explicit tie-breaking and audit evidence
- Deterministic Hard-Constraint Validation Engine (`ValidationService`, `validate_candidate_action`, `validate_decision_actions`) screening candidate actions against physical and business policies (`WAREHOUSE_CAPACITY`, active statuses, supplier eligibility, budget ceilings, quantity bounds) with traceable PASS, FAIL, and UNABLE_TO_EVALUATE semantics
- In-memory repositories with deep defensive copies, deterministic ordering, and Decision Graph consistency
- Comprehensive automated test suites across domain, repository, service, API, and graph integration layers (700 backend tests, 16 frontend tests)



## 30-Day Roadmap

```text
Days 1–5   Foundation
Days 6–10  Understand the Situation
Days 11–15 Model the Decision
Days 16–20 Make the Decision
Days 21–25 Trust the Decision
Days 26–30 AI + Product Finish
```

## Development

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- Docker and Docker Compose (optional for containerized runs)

### Local Setup

#### 1. Backend (FastAPI)

```bash
# Navigate to API directory
cd apps/api

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Start development server
uvicorn app.main:app --reload --port 8000
```

Verify backend health:
```bash
curl http://localhost:8000/health
```

#### 2. Frontend (Next.js)

```bash
# Navigate to Web directory
cd apps/web

# Install dependencies
npm install

# Start development server
npm run dev
```

The web application runs at [http://localhost:3000](http://localhost:3000).

### Docker Compose

To run both services using Docker Compose:

```bash
docker compose up --build
```
