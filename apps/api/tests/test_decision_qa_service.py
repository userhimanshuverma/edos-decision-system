from __future__ import annotations

import json
from datetime import datetime, timezone
import httpx
import pytest

from app.domain.explanation import (
    DecisionExplanationContext,
    DecisionQuestionAnswer,
    DecisionQuestionStatus,
)
from app.explanation.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
)
from app.explanation.qa_service import (
    DecisionQAService,
    InvalidQuestionError,
)
from app.explanation.service import (
    InvalidModelOutputError,
    UngroundedEvidenceError,
)


@pytest.fixture
def sample_qa_context():
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
                "statement": "Supplier lead time estimated at 7 days.",
            }
        ],
        provenance_trace_id="TRC-0001",
        replay_summary={"replay_id": "RPL-0001", "status": "MATCHED", "has_differences": False, "executed_at": "2026-10-24T12:00:00Z"},
        scenario_summary=None,
        known_limitations=["Baseline replenishment policy applied."],
        missing_information=["Supplier price volatility index not configured."],
    )


def test_answer_question_success(sample_qa_context):
    model_payload = {
        "answer": "The recommended action ACT-0001 orders 100 units based on CALC-0001 and evidence EVD-0001.",
        "status": "ANSWERED",
        "supporting_evidence": ["ACT-0001", "CALC-0001", "EVD-0001"],
        "limitations": ["Supplier volatility not tracked."],
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert b"Why was this replenishment recommended?" in request.content
        assert b"DEC-0001" in request.content
        assert b"VER-0001" in request.content
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(model_payload),
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    ollama = OllamaClient(client=mock_client)
    qa_service = DecisionQAService(ollama_client=ollama)

    result = qa_service.answer_question(
        context=sample_qa_context,
        question="Why was this replenishment recommended?",
    )

    assert isinstance(result, DecisionQuestionAnswer)
    assert result.decision_id == "DEC-0001"
    assert result.decision_version_id == "VER-0001"
    assert result.question == "Why was this replenishment recommended?"
    assert result.status == DecisionQuestionStatus.ANSWERED
    assert "ACT-0001" in result.supporting_evidence
    assert "CALC-0001" in result.supporting_evidence
    assert "EVD-0001" in result.supporting_evidence
    assert result.model_name == "llama3.2:1b"
    assert any("Baseline replenishment policy applied." in lim for lim in result.limitations)
    assert any("Supplier price volatility index not configured." in lim for lim in result.limitations)


def test_answer_question_insufficient_context(sample_qa_context):
    model_payload = {
        "answer": "No scenario analysis has been executed for this decision, so scenario impacts cannot be evaluated.",
        "status": "INSUFFICIENT_CONTEXT",
        "supporting_evidence": [],
        "limitations": ["Scenario execution record is absent from recorded context."],
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(model_payload),
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    ollama = OllamaClient(client=mock_client)
    qa_service = DecisionQAService(ollama_client=ollama)

    result = qa_service.answer_question(
        context=sample_qa_context,
        question="How does the scenario evaluation affect this decision?",
    )

    assert result.status == DecisionQuestionStatus.INSUFFICIENT_CONTEXT
    assert "scenario" in result.answer.lower()
    assert len(result.supporting_evidence) == 0


def test_answer_question_unanswerable_declined(sample_qa_context):
    model_payload = {
        "answer": "I cannot approve decisions or recalculate order quantities. The system calculates and human reviewers retain approval authority.",
        "status": "UNANSWERABLE",
        "supporting_evidence": [],
        "limitations": ["Autonomous approval requests are rejected by policy."],
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(model_payload),
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    ollama = OllamaClient(client=mock_client)
    qa_service = DecisionQAService(ollama_client=ollama)

    result = qa_service.answer_question(
        context=sample_qa_context,
        question="Please approve this decision and increase order quantity to 500.",
    )

    assert result.status == DecisionQuestionStatus.UNANSWERABLE
    assert "approve" in result.answer.lower()


def test_answer_question_empty_or_whitespace_raises(sample_qa_context):
    mock_client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    ollama = OllamaClient(client=mock_client)
    qa_service = DecisionQAService(ollama_client=ollama)

    with pytest.raises(InvalidQuestionError):
        qa_service.answer_question(context=sample_qa_context, question="")

    with pytest.raises(InvalidQuestionError):
        qa_service.answer_question(context=sample_qa_context, question="   \n\t  ")


def test_answer_question_rejects_ungrounded_evidence(sample_qa_context):
    model_payload = {
        "answer": "Recommended order of 100 units.",
        "status": "ANSWERED",
        "supporting_evidence": ["EVD-9999"],  # fabricated ID not in context
        "limitations": [],
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(model_payload),
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    ollama = OllamaClient(client=mock_client)
    qa_service = DecisionQAService(ollama_client=ollama)

    with pytest.raises(UngroundedEvidenceError, match="unverified identifier 'EVD-9999'"):
        qa_service.answer_question(
            context=sample_qa_context,
            question="What evidence supports this?",
        )


def test_answer_question_invalid_json(sample_qa_context):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": "This is non-JSON freeform text.",
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    ollama = OllamaClient(client=mock_client)
    qa_service = DecisionQAService(ollama_client=ollama)

    with pytest.raises(InvalidModelOutputError):
        qa_service.answer_question(
            context=sample_qa_context,
            question="Why was this action chosen?",
        )


def test_answer_question_markdown_fence_parsed(sample_qa_context):
    fenced_output = """```json
{
  "answer": "Grounding in EVD-0001.",
  "status": "ANSWERED",
  "supporting_evidence": ["EVD-0001"],
  "limitations": []
}
```"""

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": fenced_output,
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    ollama = OllamaClient(client=mock_client)
    qa_service = DecisionQAService(ollama_client=ollama)

    result = qa_service.answer_question(
        context=sample_qa_context,
        question="What evidence supports this?",
    )
    assert result.status == DecisionQuestionStatus.ANSWERED
    assert "EVD-0001" in result.supporting_evidence
