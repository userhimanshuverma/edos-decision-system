# System Overview

## Purpose

The **Enterprise Decision Operating System (EDOS)** is designed to provide an explainable, reproducible, and auditable operational decision platform. Modern enterprises often struggle with opaque heuristic spreadsheets, black-box algorithms, or fragmented ad-hoc decision-making processes. EDOS bridges the gap by structuring operational situations, computing deterministic outcomes, providing comprehensive evidence and audit trails, and utilizing AI strictly to synthesize natural-language explanations for human review and final approval.

## V1 Workflow

The end-to-end operational decision flow follows a disciplined sequence:

```text
Situation
→ Context
→ Actions
→ Validation
→ Scenarios
→ Result
→ Evidence
→ Provenance
→ AI Explanation
→ Human Approval
```

1. **Situation**: Ingestion and identification of the operational event or triggering state.
2. **Context**: Assembly of relevant operational context, business parameters, and state data.
3. **Actions**: Identification of admissible candidate actions and intervention choices.
4. **Validation**: Rule-based screening ensuring candidate actions satisfy hard constraints and policies.
5. **Scenarios**: Simulation and impact modeling across potential decisions and counterfactuals.
6. **Result**: Formulation of the recommended decision output and trade-off metrics.
7. **Evidence**: Fact-based supporting calculations, input citations, and historical reference points.
8. **Provenance**: Complete lineage capturing input data versions, rule versions, and execution timestamps.
9. **AI Explanation**: Clear narrative synthesis translating numerical outputs into human-readable rationale.
10. **Human Approval**: Final sign-off, rejection, or escalation by an authorized human decision-maker.

## Target Architecture

The target V1 system architecture is structured as follows:

```text
Web UI
    ↓
FastAPI
    ↓
Decision Runtime
    ├── Context Engine
    ├── Decision Engine
    └── Scenario Engine
    ↓
Validation
    ↓
Decision Result
    ├── Evidence
    ├── Risk
    └── Provenance
    ↓
AI Explanation
    ↓
Human Approval
```

> **Note**: This represents the target V1 architecture. Day 1 establishes the foundational communication layer, repository conventions, and basic health validation. Specific domain engines and AI integrations are scheduled for subsequent roadmap phases.

## Architectural Principles

### 1. Modular before distributed
Start as a modular monolith. Avoid distributed systems overhead, message buses, or premature microservices until clear scale or domain boundaries demonstrate the requirement.

### 2. Deterministic decision logic
Numerical decisions and candidate evaluations must strictly originate from deterministic, verifiable system logic.

### 3. AI explains
AI is used to explain structured system results and assist in natural-language interaction. AI must never serve as the unconstrained source of truth for numerical calculations or decisions.

### 4. Reproducibility
Every decision outcome must be reproducible from its recorded inputs, configuration rules, and engine versioning.

### 5. Traceability
The system must maintain transparent provenance and data lineage showing exactly how every calculation and recommendation was produced.

### 6. Human-in-the-loop
EDOS empowers human operators rather than autonomously bypassing human governance. Final operational approval remains with the human stakeholder.

### 7. Incremental architecture
Only introduce operational infrastructure, data persistence, or third-party dependencies when the concrete product phase requires them.
