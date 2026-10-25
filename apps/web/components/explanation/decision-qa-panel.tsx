"use client";

import React, { useState } from "react";
import type { DecisionQuestionResponse } from "../../lib/types/qa";
import { askDecisionQuestion, DecisionQuestionApiError } from "../../lib/api/qa";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { LoadingState } from "../ui/loading-state";

export interface DecisionQAPanelProps {
  initialDecisionId?: string;
  initialVersionId?: string;
  className?: string;
}

const PRESET_QUESTIONS = [
  "Why was this replenishment recommended?",
  "What recorded evidence supports this recommendation?",
  "Which constraints affect this decision?",
  "What are the key risks or limitations?",
  "What information is missing from the record?",
];

export function DecisionQAPanel({
  initialDecisionId = "DEC-0001",
  initialVersionId,
  className = "",
}: DecisionQAPanelProps) {
  const [decisionId, setDecisionId] = useState<string>(initialDecisionId);
  const [versionId, setVersionId] = useState<string>(initialVersionId || "");
  const [question, setQuestion] = useState<string>("");
  const [qaResult, setQaResult] = useState<DecisionQuestionResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  const handleSubmit = async (e?: React.FormEvent, presetQ?: string) => {
    if (e) e.preventDefault();
    const targetQ = (presetQ || question).trim();
    const targetId = decisionId.trim();
    if (!targetId || !targetQ) return;

    if (presetQ) {
      setQuestion(presetQ);
    }

    setIsLoading(true);
    setError(null);
    setErrorStatus(null);

    try {
      const res = await askDecisionQuestion(
        targetId,
        targetQ,
        versionId.trim() || undefined
      );
      setQaResult(res);
    } catch (err: unknown) {
      if (err instanceof DecisionQuestionApiError) {
        setError(err.message);
        setErrorStatus(err.statusCode);
      } else if (err instanceof Error) {
        setError(err.message);
        setErrorStatus(null);
      } else {
        setError("An unexpected error occurred while processing your question.");
        setErrorStatus(null);
      }
      setQaResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card
      title="Decision Q&A (Day 27 Local LLM)"
      description="Auditable natural-language inquiry grounded strictly in recorded decision data and constraints. The system calculates. AI explains. Humans approve."
      headerAction={
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Badge variant="neutral">Local Ollama</Badge>
          <Badge variant="default">Day 27</Badge>
          {qaResult && (
            <Badge
              variant={
                qaResult.status === "ANSWERED"
                  ? "success"
                  : qaResult.status === "INSUFFICIENT_CONTEXT"
                  ? "warning"
                  : "neutral"
              }
            >
              {qaResult.status}
            </Badge>
          )}
        </div>
      }
      className={`edos-decision-qa-panel ${className}`.trim()}
    >
      {/* Scope Inputs */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "12px",
          alignItems: "center",
          marginBottom: "12px",
          padding: "10px 14px",
          background: "var(--surface-subtle, #1a1e24)",
          borderRadius: "var(--radius-md, 6px)",
          border: "1px solid var(--border-subtle, #2d333b)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <label
            htmlFor="qa-decision-id-input"
            style={{
              fontSize: "0.8125rem",
              fontWeight: 600,
              color: "var(--foreground-muted, #8b949e)",
            }}
          >
            Decision ID:
          </label>
          <input
            id="qa-decision-id-input"
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
            htmlFor="qa-version-id-input"
            style={{
              fontSize: "0.8125rem",
              fontWeight: 600,
              color: "var(--foreground-muted, #8b949e)",
            }}
          >
            Version (opt):
          </label>
          <input
            id="qa-version-id-input"
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
      </div>

      {/* Preset Questions */}
      <div style={{ marginBottom: "12px" }}>
        <div
          style={{
            fontSize: "0.75rem",
            fontWeight: 600,
            color: "var(--foreground-muted, #8b949e)",
            marginBottom: "6px",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
          }}
        >
          Suggested Inquiries:
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {PRESET_QUESTIONS.map((pq, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSubmit(undefined, pq)}
              disabled={isLoading || !decisionId.trim()}
              style={{
                fontSize: "0.75rem",
                padding: "4px 8px",
                borderRadius: "12px",
                border: "1px solid var(--border-subtle, #30363d)",
                background: "var(--surface-subtle, #161b22)",
                color: "var(--foreground-muted, #8b949e)",
                cursor: isLoading ? "not-allowed" : "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {pq}
            </button>
          ))}
        </div>
      </div>

      {/* Question Form */}
      <form
        onSubmit={handleSubmit}
        style={{
          display: "flex",
          gap: "8px",
          marginBottom: "16px",
        }}
      >
        <input
          id="qa-question-input"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about this decision's recommendation, evidence, or constraints..."
          disabled={isLoading}
          style={{
            flex: 1,
            padding: "8px 12px",
            fontSize: "0.875rem",
            borderRadius: "6px",
            border: "1px solid var(--border-default, #30363d)",
            background: "var(--surface-base, #0d1117)",
            color: "var(--foreground, #c9d1d9)",
          }}
        />
        <Button
          type="submit"
          variant="primary"
          size="sm"
          disabled={isLoading || !decisionId.trim() || !question.trim()}
        >
          {isLoading ? "Inquiring..." : "Ask Question"}
        </Button>
      </form>

      {/* Loading state */}
      {isLoading && (
        <div style={{ padding: "20px 16px" }}>
          <LoadingState
            label="Inquiring decision context..."
            sublabel="Grounded interpretation synthesized from recorded calculation, constraints, and evidence"
          />
        </div>
      )}

      {/* Error state */}
      {!isLoading && error && (
        <div
          role="alert"
          style={{
            padding: "14px 16px",
            marginBottom: "16px",
            background: "rgba(248, 81, 73, 0.1)",
            border: "1px solid rgba(248, 81, 73, 0.4)",
            borderRadius: "6px",
            color: "#f85149",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 600, marginBottom: "4px" }}>
            <span>⚠️ Decision Q&A Incomplete</span>
            {errorStatus && (
              <Badge variant="danger">HTTP {errorStatus}</Badge>
            )}
          </div>
          <p style={{ fontSize: "0.875rem", margin: 0, color: "var(--foreground, #c9d1d9)" }}>
            {error}
          </p>
          {errorStatus === 503 && (
            <p style={{ fontSize: "0.8125rem", marginTop: "6px", color: "var(--foreground-muted, #8b949e)" }}>
              Ensure local Ollama is running (`ollama serve`) and the configured model is available.
            </p>
          )}
        </div>
      )}

      {/* Result View */}
      {!isLoading && qaResult && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "14px",
            animation: "fadeIn 0.2s ease-in-out",
          }}
        >
          {/* Answer Card */}
          <div
            style={{
              padding: "16px",
              background: "var(--surface-base, #0d1117)",
              borderRadius: "6px",
              border: "1px solid var(--border-default, #30363d)",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                color: "var(--foreground-muted, #8b949e)",
                marginBottom: "8px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <span>INQUIRY: &quot;{qaResult.question}&quot;</span>
              <span>Model: {qaResult.model_name}</span>
            </div>

            <div
              style={{
                fontSize: "0.9375rem",
                lineHeight: "1.6",
                color: "var(--foreground, #c9d1d9)",
                whiteSpace: "pre-wrap",
              }}
            >
              {qaResult.answer}
            </div>
          </div>

          {/* Supporting Evidence Citations */}
          {qaResult.supporting_evidence && qaResult.supporting_evidence.length > 0 && (
            <div
              style={{
                padding: "12px 14px",
                background: "var(--surface-subtle, #161b22)",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle, #30363d)",
              }}
            >
              <div
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "var(--foreground-muted, #8b949e)",
                  marginBottom: "8px",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                Validated Supporting Citations:
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {qaResult.supporting_evidence.map((cit, idx) => (
                  <Badge key={idx} variant="info">
                    {cit}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Limitations / Incomplete Context */}
          {qaResult.limitations && qaResult.limitations.length > 0 && (
            <div
              style={{
                padding: "12px 14px",
                background: "rgba(227, 179, 65, 0.08)",
                borderRadius: "6px",
                border: "1px solid rgba(227, 179, 65, 0.25)",
              }}
            >
              <div
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "#e3b341",
                  marginBottom: "6px",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                Explicit Context Limitations:
              </div>
              <ul
                style={{
                  margin: 0,
                  paddingLeft: "18px",
                  fontSize: "0.8125rem",
                  color: "var(--foreground-muted, #8b949e)",
                  lineHeight: "1.5",
                }}
              >
                {qaResult.limitations.map((lim, idx) => (
                  <li key={idx}>{lim}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Read-Only Governance Disclaimer */}
          <div
            style={{
              padding: "8px 12px",
              background: "rgba(56, 139, 253, 0.08)",
              borderRadius: "4px",
              border: "1px solid rgba(56, 139, 253, 0.2)",
              fontSize: "0.75rem",
              color: "var(--foreground-muted, #8b949e)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>🔒 Read-only explanation. The system calculates. AI explains. Humans approve.</span>
            <span>Answered: {new Date(qaResult.generated_at).toLocaleTimeString()}</span>
          </div>
        </div>
      )}
    </Card>
  );
}
