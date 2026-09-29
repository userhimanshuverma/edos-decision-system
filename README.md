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

**Day 1: Foundation Phase**

The repository currently establishes:
- Standard repository layout and conventions
- Python + FastAPI backend foundation with `/health` validation
- Next.js + React + TypeScript web foundation
- Target architecture documentation and operational principles
- Development configuration, testing setup, and minimal Docker definitions

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
