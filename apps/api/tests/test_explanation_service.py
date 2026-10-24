from __future__ import annotations

import json
from datetime import datetime, timezone
import httpx
import pytest

from app.domain.explanation import DecisionExplanationContext
from app.explanation.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
)
from app.explanation.service import (
    ExplanationService,
    InsufficientContextError,
    InvalidModelOutputError,
    UngroundedEvidenceError,
)


@pytest.fixture
def sample_context():
    return DecisionExplanationContext(
        decision_id="DEC-0001",
        decision_version_id="VER-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        decision_status="READY",
        recommendation_status="RECOMMENDED",
        recommended_action_id="ACT-0001",
        recommended_action_type="PLACE_ORDER",
        selection_rule="LEXICOGRAPHIC_DOMINANCE",
        selection_rationale="Orders 100 units from primary supplier to eliminate stockout risk.",
        action_parameters={"quantity": 100, "supplier_id": "sup-001"},
        calculation_results=[
            {
                "id": "CALC-0001",
                "description": "Calculated replenishment quantity: 100 units",
                "value": 100,
                "unit": "units",
            }
        ],
        constraint_results=[
            {
                "constraint_name": "Warehouse Capacity",
                "status": "PASS",
                "reason": "Fits within warehouse limits",
            }
        ],
        evidence_items=[
            {
                "id": "EVD-0001",
                "description": "Current stock: 40 units",
                "value": 40,
                "unit": "units",
            }
        ],
        assumptions=[
            {
                "id": "ASM-0001",
                "statement": "Demand rate stationary at 10 units/day",
            }
        ],
        known_limitations=["Baseline replenishment policy applied."],
        missing_information=[],
        collected_at=datetime.now(timezone.utc),
    )


def test_generate_explanation_success(sample_context):
    model_response_json = {
        "recommendation_summary": "Place order of 100 units with primary supplier sup-001.",
        "reasoning_summary": "Current stock (40 units, EVD-0001) is below safety levels. An order of 100 units (CALC-0001) restores runway while respecting capacity.",
        "supporting_evidence": ["EVD-0001", "CALC-0001", "ACT-0001"],
        "risks_and_constraints": ["Warehouse capacity constraint satisfied."],
        "assumptions_and_missing_information": ["Daily demand stationary at 10 units/day (ASM-0001)."],
        "review_considerations": ["Verify supplier lead time before formal dispatch."],
        "limitations": ["Assumes no sudden demand surges."],
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(model_response_json),
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    ollama = OllamaClient(client=client)
    service = ExplanationService(ollama_client=ollama)

    explanation = service.generate_explanation(sample_context)

    assert explanation.decision_id == "DEC-0001"
    assert explanation.decision_version_id == "VER-0001"
    assert "ACT-0001" in explanation.recommendation_summary
    assert "EVD-0001" in explanation.supporting_evidence
    assert "CALC-0001" in explanation.supporting_evidence
    assert explanation.model_name == "llama3.2:1b"
    assert any("Baseline replenishment policy applied." in lim for lim in explanation.limitations)


def test_generate_explanation_ungrounded_evidence_rejected(sample_context):
    model_response_json = {
        "recommendation_summary": "Place order of 100 units.",
        "reasoning_summary": "Supported by fabricated facts.",
        "supporting_evidence": ["EVD-9999"],  # Unknown ID!
        "risks_and_constraints": [],
        "assumptions_and_missing_information": [],
        "review_considerations": [],
        "limitations": [],
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(model_response_json),
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    ollama = OllamaClient(client=client)
    service = ExplanationService(ollama_client=ollama)

    with pytest.raises(UngroundedEvidenceError, match="unverified identifier 'EVD-9999'"):
        service.generate_explanation(sample_context)


def test_generate_explanation_invalid_json(sample_context):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": "Not valid json at all",
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    ollama = OllamaClient(client=client)
    service = ExplanationService(ollama_client=ollama)

    with pytest.raises(InvalidModelOutputError, match="Failed to extract JSON"):
        service.generate_explanation(sample_context)


def test_generate_explanation_schema_violation(sample_context):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": '{"only_field": "missing required summaries"}',
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    ollama = OllamaClient(client=client)
    service = ExplanationService(ollama_client=ollama)

    with pytest.raises(InvalidModelOutputError, match="does not conform to the explanation contract"):
        service.generate_explanation(sample_context)


def test_generate_explanation_insufficient_context():
    context_no_rec = DecisionExplanationContext(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        decision_status="DRAFT",
        recommendation_status=None,
        recommended_action_id=None,
        collected_at=datetime.now(timezone.utc),
    )

    ollama = OllamaClient()
    service = ExplanationService(ollama_client=ollama)

    with pytest.raises(InsufficientContextError, match="no recorded recommendation to explain"):
        service.generate_explanation(context_no_rec)


def test_prompt_includes_strict_guardrails(sample_context):
    ollama = OllamaClient()
    service = ExplanationService(ollama_client=ollama)
    prompt = service.build_prompt(sample_context)

    assert "DEC-0001" in prompt
    assert "prod-001" in prompt
    assert "wh-001" in prompt
    assert "ACT-0001" in prompt
