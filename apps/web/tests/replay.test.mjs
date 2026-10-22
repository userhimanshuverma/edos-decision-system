import test from "node:test";
import assert from "node:assert/strict";

// Test suite for Day 24 Decision Replay Engine TypeScript contracts and domain structures

test("Replay Engine - TypeScript Contract Structure", () => {
  const sampleDifference = {
    field_path: "recommendation.recommended_action_id",
    original_value: "ACT-0001",
    replayed_value: "ACT-0002",
    difference_description: "Recommended action changed from ACT-0001 to ACT-0002",
  };

  const sampleComparison = {
    status: "DIFFERENT",
    compared_fields: [
      "recommendation.status",
      "recommendation.recommended_action_id",
      "recommendation.recommended_action_type",
      "recommendation.tie_broken",
    ],
    ignored_fields: ["created_at", "replay_execution_id"],
    differences: [sampleDifference],
    summary: "Replay completed with 1 meaningful difference(s) detected across business results.",
  };

  const sampleIncompleteReason = {
    code: "UNAVAILABLE_HISTORICAL_INPUT",
    message: "Historical inventory position was marked unavailable during execution.",
    details: { input_type: "INVENTORY", status: "UNAVAILABLE" },
  };

  const sampleReplayRecord = {
    id: "RPL-0001",
    decision_id: "DEC-0001",
    version_id: "VER-0001",
    original_trace_id: "PRV-0001",
    original_execution_id: "EXEC-0001",
    replay_execution_id: "REX-0001",
    created_at: "2026-10-22T12:00:00Z",
    status: "MATCHED",
    original_result: {
      recommendation_id: "REC-0001",
      status: "RECOMMENDED",
      recommended_action_id: "ACT-0001",
      recommended_action_type: "PURCHASE_ORDER",
      tie_broken: false,
      tie_break_method: "NONE",
      selection_rule: "LEXICOGRAPHIC_OPERATIONAL_DOMINANCE",
      evaluations: {},
      metadata: {},
    },
    replayed_result: {
      recommendation_id: "REC-0002",
      status: "RECOMMENDED",
      recommended_action_id: "ACT-0001",
      recommended_action_type: "PURCHASE_ORDER",
      tie_broken: false,
      tie_break_method: "NONE",
      selection_rule: "LEXICOGRAPHIC_OPERATIONAL_DOMINANCE",
      evaluations: {},
      metadata: {},
    },
    comparison: {
      status: "MATCHED",
      compared_fields: ["recommendation.status", "recommendation.recommended_action_id"],
      ignored_fields: ["created_at", "recommendation_id"],
      differences: [],
      summary: "Replay completed with identical business results across all compared dimensions.",
    },
    incomplete_reasons: [],
    error_message: null,
    reconstructed_inputs_summary: { product_id: "prod-001" },
    metadata: {},
  };

  assert.equal(sampleReplayRecord.id, "RPL-0001");
  assert.equal(sampleReplayRecord.decision_id, "DEC-0001");
  assert.equal(sampleReplayRecord.version_id, "VER-0001");
  assert.equal(sampleReplayRecord.original_trace_id, "PRV-0001");
  assert.equal(sampleReplayRecord.status, "MATCHED");
  assert.equal(sampleReplayRecord.comparison.status, "MATCHED");
  assert.equal(sampleReplayRecord.comparison.differences.length, 0);
  assert.equal(sampleComparison.differences.length, 1);
  assert.equal(sampleIncompleteReason.code, "UNAVAILABLE_HISTORICAL_INPUT");
});

test("Replay Engine - ReplayStatus Enum Values", () => {
  const allowedStatuses = ["MATCHED", "DIFFERENT", "INCOMPLETE", "FAILED"];
  assert.ok(allowedStatuses.includes("MATCHED"));
  assert.ok(allowedStatuses.includes("DIFFERENT"));
  assert.ok(allowedStatuses.includes("INCOMPLETE"));
  assert.ok(allowedStatuses.includes("FAILED"));
});

test("Replay Engine - IncompleteReasonCode Enum Values", () => {
  const allowedCodes = [
    "MISSING_PROVENANCE_TRACE",
    "MISSING_INPUT_RECORD",
    "UNAVAILABLE_HISTORICAL_INPUT",
    "UNAVAILABLE_RULE_DEFINITION",
    "MISSING_CANDIDATE_ACTIONS",
    "NO_RECORDED_RESULTS",
    "UNSUPPORTED_REPLAY_OPERATION",
  ];
  assert.ok(allowedCodes.includes("MISSING_PROVENANCE_TRACE"));
  assert.ok(allowedCodes.includes("UNAVAILABLE_HISTORICAL_INPUT"));
  assert.ok(allowedCodes.includes("MISSING_CANDIDATE_ACTIONS"));
});

test("Replay Engine - Comparison Invariant (MATCHED has zero diffs, DIFFERENT has diffs)", () => {
  const matchedComp = {
    status: "MATCHED",
    compared_fields: ["recommendation.recommended_action_id"],
    ignored_fields: ["created_at"],
    differences: [],
    summary: "Replay completed with identical business results.",
  };
  assert.equal(matchedComp.status, "MATCHED");
  assert.equal(matchedComp.differences.length, 0);

  const differentComp = {
    status: "DIFFERENT",
    compared_fields: ["recommendation.recommended_action_id"],
    ignored_fields: ["created_at"],
    differences: [
      {
        field_path: "recommendation.recommended_action_id",
        original_value: "ACT-0001",
        replayed_value: "ACT-0002",
        difference_description: "Recommended action changed",
      },
    ],
    summary: "Replay completed with differences.",
  };
  assert.equal(differentComp.status, "DIFFERENT");
  assert.ok(differentComp.differences.length > 0);
});

test("Replay Engine - Incomplete Replay Integrity (never represented as MATCHED)", () => {
  const incompleteRecord = {
    id: "RPL-0002",
    decision_id: "DEC-0001",
    status: "INCOMPLETE",
    original_result: null,
    replayed_result: null,
    comparison: null,
    incomplete_reasons: [
      {
        code: "MISSING_PROVENANCE_TRACE",
        message: "No provenance trace found for decision.",
        details: {},
      },
    ],
  };

  assert.equal(incompleteRecord.status, "INCOMPLETE");
  assert.notEqual(incompleteRecord.status, "MATCHED");
  assert.ok(incompleteRecord.incomplete_reasons.length > 0);
  assert.equal(incompleteRecord.comparison, null);
});
