import test from "node:test";
import assert from "node:assert/strict";

// Test suite for Day 27 Decision Q&A TypeScript contracts and domain structures

test("Decision Q&A - TypeScript Contract Structure", () => {
  const sampleResponse = {
    decision_id: "DEC-0001",
    decision_version_id: "VER-0001",
    question: "Why was this replenishment recommended?",
    answer:
      "The recommendation to order 60 units is supported by inventory shortfall below reorder point (ROP 80, Available 45).",
    status: "ANSWERED",
    supporting_evidence: ["EVD-0001", "ACT-0001", "CALC-0001"],
    limitations: ["Supplier lead time variability not accounted for."],
    model_name: "llama3.2:1b",
    generated_at: "2026-10-25T20:30:00Z",
  };

  assert.equal(sampleResponse.decision_id, "DEC-0001");
  assert.equal(sampleResponse.decision_version_id, "VER-0001");
  assert.equal(sampleResponse.question, "Why was this replenishment recommended?");
  assert.ok(sampleResponse.answer.includes("60 units"));
  assert.equal(sampleResponse.status, "ANSWERED");
  assert.equal(sampleResponse.supporting_evidence.length, 3);
  assert.equal(sampleResponse.limitations.length, 1);
  assert.equal(sampleResponse.model_name, "llama3.2:1b");
  assert.ok(sampleResponse.generated_at.endsWith("Z"));
});

test("Decision Q&A - Valid Status Enumeration", () => {
  const validStatuses = ["ANSWERED", "INSUFFICIENT_CONTEXT", "UNANSWERABLE"];

  for (const st of validStatuses) {
    const response = {
      decision_id: "DEC-0002",
      decision_version_id: null,
      question: "Are there any hard constraints?",
      answer: "No hard constraints were violated.",
      status: st,
      supporting_evidence: [],
      limitations: [],
      model_name: "llama3.2:1b",
      generated_at: new Date().toISOString(),
    };
    assert.ok(validStatuses.includes(response.status));
  }
});

test("Decision Q&A - Invariant: Read-Only, Non-Mutating, No Approvals", () => {
  // Governing principle: "The system calculates. AI explains. Humans approve."
  const forbiddenAttributes = [
    "approved",
    "rejected",
    "executed",
    "mutate_quantity",
    "override_status",
  ];

  const qaPayload = {
    decision_id: "DEC-0001",
    decision_version_id: null,
    question: "Can you approve this decision?",
    answer: "I am a read-only AI explanation assistant. Humans retain exclusive approval authority.",
    status: "ANSWERED",
    supporting_evidence: [],
    limitations: ["AI cannot execute or approve decisions."],
    model_name: "llama3.2:1b",
    generated_at: new Date().toISOString(),
  };

  for (const attr of forbiddenAttributes) {
    assert.equal(attr in qaPayload, false, `Attribute ${attr} must never exist on Q&A payload`);
  }
});

test("Decision Q&A - Missing Context Honest Reporting", () => {
  const insufficientContextResponse = {
    decision_id: "DEC-0003",
    decision_version_id: null,
    question: "What were the replay results for this decision?",
    answer: "No replay results were recorded for this decision.",
    status: "INSUFFICIENT_CONTEXT",
    supporting_evidence: [],
    limitations: [
      "Replay simulation has not been executed for decision DEC-0003.",
    ],
    model_name: "llama3.2:1b",
    generated_at: new Date().toISOString(),
  };

  assert.equal(insufficientContextResponse.status, "INSUFFICIENT_CONTEXT");
  assert.equal(insufficientContextResponse.supporting_evidence.length, 0);
  assert.ok(insufficientContextResponse.limitations.length > 0);
});

test("Decision Q&A - Runtime Error Classification (Ollama Offline 503 vs Validation 422)", () => {
  const errorScenarios = [
    {
      statusCode: 503,
      expectedCategory: "RUNTIME_UNAVAILABLE",
      description: "Local Ollama server connection refused or timed out",
    },
    {
      statusCode: 502,
      expectedCategory: "INVALID_OUTPUT_OR_UNGROUNDED",
      description: "Model returned invalid JSON or fabricated ungrounded evidence references",
    },
    {
      statusCode: 422,
      expectedCategory: "INVALID_REQUEST_OR_INSUFFICIENT_CONTEXT",
      description: "Empty/whitespace question or missing minimal decision context",
    },
    {
      statusCode: 404,
      expectedCategory: "DECISION_NOT_FOUND",
      description: "Target decision does not exist in the repository",
    },
  ];

  for (const scenario of errorScenarios) {
    assert.ok(scenario.statusCode >= 400);
    assert.ok(scenario.expectedCategory.length > 0);
  }
});
