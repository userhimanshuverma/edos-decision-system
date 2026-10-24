"use client";

import React, { useState } from "react";
import type { DecisionExplanation } from "../../lib/types/explanation";
import { generateDecisionExplanation, ExplanationApiError } from "../../lib/api/explanation";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { LoadingState } from "../ui/loading-state";

export interface ExplanationPanelProps {
  initialDecisionId?: string;
  initialVersionId?: string;
  className?: string;
}

export function ExplanationPanel({
  initialDecisionId = "DEC-0001",
  initialVersionId,
  className = "",
}: ExplanationPanelProps) {
  const [decisionId, setDecisionId] = useState<string>(initialDecisionId);
  const [versionId, setVersionId] = useState<string>(initialVersionId || "");
  const [explanation, setExplanation] = useState<DecisionExplanation | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  const handleGenerate = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const targetId = decisionId.trim();
    if (!targetId) return;

    setIsLoading(true);
    setError(null);
    setErrorStatus(null);

    try {
      const res = await generateDecisionExplanation(
        targetId,
        versionId.trim() || undefined
      );
      setExplanation(res);
    } catch (err: unknown) {
      if (err instanceof ExplanationApiError) {
        setError(err.message);
        setErrorStatus(err.statusCode);
      } else if (err instanceof Error) {
        setError(err.message);
        setErrorStatus(null);
      } else {
        setError("An unexpected error occurred while requesting an explanation.");
        setErrorStatus(null);
      }
      setExplanation(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card
      title="AI Decision Explanation (Day 26 Local LLM)"
      description="Auditable interpretation generated via local Ollama runtime. The system calculates. AI explains. Humans approve."
      headerAction={
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Badge variant="neutral">Local Ollama</Badge>
          <Badge variant="default">Day 26</Badge>
        </div>
      }
      className={`edos-explanation-panel ${className}`.trim()}
    >
      {/* Control bar */}
      <form
        onSubmit={handleGenerate}
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "12px",
          alignItems: "center",
          marginBottom: "16px",
          padding: "12px 16px",
          background: "var(--surface-subtle, #1a1e24)",
          borderRadius: "var(--radius-md, 6px)",
          border: "1px solid var(--border-subtle, #2d333b)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <label
            htmlFor="decision-id-input"
            style={{
              fontSize: "0.8125rem",
              fontWeight: 600,
              color: "var(--foreground-muted, #8b949e)",
            }}
          >
            Decision ID:
          </label>
          <input
            id="decision-id-input"
            type="text"
            value={decisionId}
            onChange={(e) => setDecisionId(e.target.value)}
            placeholder="e.g. DEC-0001"
            style={{
              padding: "6px 10px",
              fontSize: "0.8125rem",
              borderRadius: "4px",
              border: "1px solid var(--border-default, #30363d)",
              background: "var(--surface-base, #0d1117)",
              color: "var(--foreground, #c9d1d9)",
            }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <label
            htmlFor="version-id-input"
            style={{
              fontSize: "0.8125rem",
              fontWeight: 600,
              color: "var(--foreground-muted, #8b949e)",
            }}
          >
            Version (opt):
          </label>
          <input
            id="version-id-input"
            type="text"
            value={versionId}
            onChange={(e) => setVersionId(e.target.value)}
            placeholder="e.g. VER-0001"
            style={{
              padding: "6px 10px",
              fontSize: "0.8125rem",
              borderRadius: "4px",
              border: "1px solid var(--border-default, #30363d)",
              background: "var(--surface-base, #0d1117)",
              color: "var(--foreground, #c9d1d9)",
            }}
          />
        </div>

        <Button
          type="submit"
          variant="primary"
          size="sm"
          disabled={isLoading || !decisionId.trim()}
        >
          {isLoading ? "Generating Explanation..." : "Generate AI Explanation"}
        </Button>
      </form>

      {/* Loading state */}
      {isLoading && (
        <div style={{ padding: "24px 16px" }}>
          <LoadingState
            label="Requesting structured explanation from local Ollama..."
            sublabel="Synthesizing recorded calculations, constraints, evidence, and audit logs without modifying business logic"
          />
        </div>
      )}

      {/* Error state */}
      {!isLoading && error && (
        <div
          role="alert"
          style={{
            padding: "16px",
            marginBottom: "16px",
            background: "rgba(248, 81, 73, 0.1)",
            border: "1px solid rgba(248, 81, 73, 0.4)",
            borderRadius: "6px",
            color: "#f85149",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 600, marginBottom: "4px" }}>
            <span>⚠️ Explanation Generation Failed</span>
            {errorStatus && (
              <Badge variant="danger">HTTP {errorStatus}</Badge>
            )}
          </div>
          <p style={{ fontSize: "0.875rem", margin: 0, color: "var(--foreground, #c9d1d9)" }}>
            {error}
          </p>
          {errorStatus === 503 && (
            <p style={{ fontSize: "0.8125rem", marginTop: "8px", color: "var(--foreground-muted, #8b949e)" }}>
              Tip: Ensure local Ollama is running (`ollama serve`) and the configured model is installed (`ollama pull llama3.2:1b`).
            </p>
          )}
        </div>
      )}

      {/* Explanation output view */}
      {!isLoading && explanation && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "16px",
            animation: "fadeIn 0.2s ease-in-out",
          }}
        >
          {/* Non-approval governance banner */}
          <div
            style={{
              padding: "10px 14px",
              background: "rgba(56, 139, 253, 0.1)",
              border: "1px solid rgba(56, 139, 253, 0.3)",
              borderRadius: "6px",
              fontSize: "0.8125rem",
              color: "var(--foreground-muted, #8b949e)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "8px",
            }}
          >
            <span>
              ℹ️ <strong>Governance Notice:</strong> AI explains recorded decision data. This summary does not constitute decision approval, rejection, or numerical re-computation.
            </span>
            <div style={{ display: "flex", gap: "6px" }}>
              <Badge variant="neutral">Model: {explanation.model_name}</Badge>
              {explanation.decision_version_id && (
                <Badge variant="default">Version: {explanation.decision_version_id}</Badge>
              )}
            </div>
          </div>

          {/* Section 1: Recommendation Summary */}
          <div
            style={{
              padding: "14px",
              background: "var(--surface-subtle, #161b22)",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle, #21262d)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
              <Badge variant="success">Deterministic Recommendation</Badge>
              <span style={{ fontSize: "0.75rem", color: "var(--foreground-muted, #8b949e)" }}>
                Calculated by EDOS engine
              </span>
            </div>
            <p style={{ margin: 0, fontSize: "0.9375rem", fontWeight: 500 }}>
              {explanation.recommendation_summary}
            </p>
          </div>

          {/* Section 2: Reasoning Narrative */}
          <div
            style={{
              padding: "14px",
              background: "var(--surface-subtle, #161b22)",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle, #21262d)",
            }}
          >
            <h4
              style={{
                margin: "0 0 8px 0",
                fontSize: "0.875rem",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "var(--foreground-muted, #8b949e)",
              }}
            >
              Grounded Decision Rationale
            </h4>
            <p style={{ margin: 0, fontSize: "0.875rem", lineHeight: 1.6, color: "var(--foreground, #c9d1d9)" }}>
              {explanation.reasoning_summary}
            </p>
          </div>

          {/* Section 3: Supporting Evidence */}
          <div
            style={{
              padding: "14px",
              background: "var(--surface-subtle, #161b22)",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle, #21262d)",
            }}
          >
            <h4
              style={{
                margin: "0 0 8px 0",
                fontSize: "0.875rem",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "var(--foreground-muted, #8b949e)",
              }}
            >
              Verified Supporting Evidence ({explanation.supporting_evidence.length})
            </h4>
            {explanation.supporting_evidence.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "0.875rem", lineHeight: 1.5 }}>
                {explanation.supporting_evidence.map((ev, idx) => (
                  <li key={idx} style={{ marginBottom: "4px" }}>
                    <code style={{ background: "rgba(110, 118, 129, 0.2)", padding: "2px 6px", borderRadius: "4px" }}>
                      {ev}
                    </code>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--foreground-muted, #8b949e)" }}>
                No explicit evidence identifiers cited.
              </p>
            )}
          </div>

          {/* Section 4: Risks & Constraints */}
          <div
            style={{
              padding: "14px",
              background: "var(--surface-subtle, #161b22)",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle, #21262d)",
            }}
          >
            <h4
              style={{
                margin: "0 0 8px 0",
                fontSize: "0.875rem",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "var(--foreground-muted, #8b949e)",
              }}
            >
              Risks & Constraints ({explanation.risks_and_constraints.length})
            </h4>
            {explanation.risks_and_constraints.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "0.875rem", lineHeight: 1.5 }}>
                {explanation.risks_and_constraints.map((item, idx) => (
                  <li key={idx} style={{ marginBottom: "4px" }}>
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--foreground-muted, #8b949e)" }}>
                No active risks or constraint violations recorded.
              </p>
            )}
          </div>

          {/* Section 5: Assumptions & Missing Information (Explicit separation) */}
          <div
            style={{
              padding: "14px",
              background: "var(--surface-subtle, #161b22)",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle, #21262d)",
            }}
          >
            <h4
              style={{
                margin: "0 0 8px 0",
                fontSize: "0.875rem",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "var(--warning, #d29922)",
              }}
            >
              Assumptions & Missing Information ({explanation.assumptions_and_missing_information.length})
            </h4>
            {explanation.assumptions_and_missing_information.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "0.875rem", lineHeight: 1.5 }}>
                {explanation.assumptions_and_missing_information.map((item, idx) => (
                  <li key={idx} style={{ marginBottom: "4px" }}>
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--foreground-muted, #8b949e)" }}>
                No ungrounded assumptions or missing context detected.
              </p>
            )}
          </div>

          {/* Section 6: Review Considerations & Limitations */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "12px",
            }}
          >
            <div
              style={{
                padding: "12px",
                background: "var(--surface-subtle, #161b22)",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle, #21262d)",
              }}
            >
              <h5 style={{ margin: "0 0 6px 0", fontSize: "0.8125rem", color: "var(--foreground-muted, #8b949e)" }}>
                Human Review Considerations
              </h5>
              <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "0.8125rem", lineHeight: 1.4 }}>
                {explanation.review_considerations.map((rc, idx) => (
                  <li key={idx} style={{ marginBottom: "2px" }}>{rc}</li>
                ))}
              </ul>
            </div>

            <div
              style={{
                padding: "12px",
                background: "var(--surface-subtle, #161b22)",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle, #21262d)",
              }}
            >
              <h5 style={{ margin: "0 0 6px 0", fontSize: "0.8125rem", color: "var(--foreground-muted, #8b949e)" }}>
                System Limitations
              </h5>
              <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "0.8125rem", lineHeight: 1.4 }}>
                {explanation.limitations.map((lim, idx) => (
                  <li key={idx} style={{ marginBottom: "2px" }}>{lim}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Footer Metadata */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontSize: "0.75rem",
              color: "var(--foreground-muted, #8b949e)",
              paddingTop: "8px",
              borderTop: "1px solid var(--border-subtle, #21262d)",
            }}
          >
            <span>Generated: {new Date(explanation.generated_at).toLocaleString()}</span>
            <span>Deterministic Engine: EDOS Core v1</span>
          </div>
        </div>
      )}
    </Card>
  );
}
