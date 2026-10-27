"use client";

import React, { useState } from "react";
import type {
  DecisionValidationRecord,
  DecisionEvidenceSheetRecord,
  DecisionProvenanceTraceRecord,
  DecisionReplayRecord,
  SectionLoadStatus,
  SectionErrorState,
} from "../../lib/types/decision";
import { executeDecisionReplay } from "../../lib/api/decision";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Tabs, TabItem } from "../ui/tabs";
import { KeyValue } from "../ui/key-value";
import { ErrorState } from "../ui/error-state";
import { LoadingState } from "../ui/loading-state";
import { EmptyState } from "../ui/empty-state";

export interface EvidenceTrustSectionProps {
  decisionId: string;
  validation: DecisionValidationRecord | null;
  validationStatus?: SectionLoadStatus;
  validationError?: SectionErrorState | null;
  onRetryValidation?: () => void;
  evidenceSheet: DecisionEvidenceSheetRecord | null;
  evidenceStatus?: SectionLoadStatus;
  evidenceError?: SectionErrorState | null;
  onRetryEvidence?: () => void;
  provenance: DecisionProvenanceTraceRecord | null;
  provenanceStatus?: SectionLoadStatus;
  provenanceError?: SectionErrorState | null;
  onRetryProvenance?: () => void;
  replay: DecisionReplayRecord | null;
  replayStatus?: SectionLoadStatus;
  replayErrorState?: SectionErrorState | null;
  onRetryReplay?: () => void;
  onRefreshReplay: () => void;
  onRevalidatePrompt?: () => void;
  isLoading?: boolean;
}

export function EvidenceTrustSection({
  decisionId,
  validation,
  validationStatus = "idle",
  validationError = null,
  onRetryValidation,
  evidenceSheet,
  evidenceStatus = "idle",
  evidenceError = null,
  onRetryEvidence,
  provenance,
  provenanceStatus = "idle",
  provenanceError = null,
  onRetryProvenance,
  replay,
  replayStatus = "idle",
  replayErrorState = null,
  onRetryReplay,
  onRefreshReplay,
  onRevalidatePrompt,
  isLoading = false,
}: EvidenceTrustSectionProps) {
  const [activeTab, setActiveTab] = useState<string>("constraints");
  const [isExecutingReplay, setIsExecutingReplay] = useState<boolean>(false);
  const [replayError, setReplayError] = useState<string | null>(null);

  const tabs: TabItem[] = [
    {
      id: "constraints",
      label: `Constraints (${validation?.action_results?.length ?? 0})`,
      badge: validationError ? "ERROR" : validation?.status === "ALL_SATISFIED" ? "PASS" : validation?.status ? "CHECK" : undefined,
    },
    {
      id: "evidence",
      label: `Evidence Sheet (${(evidenceSheet?.items?.length ?? 0) + (evidenceSheet?.assumptions?.length ?? 0)})`,
      badge: evidenceError ? "ERROR" : undefined,
    },
    {
      id: "provenance",
      label: "Provenance Trace",
      badge: provenanceError ? "ERROR" : provenance?.status || "PENDING",
    },
    {
      id: "replay",
      label: "Decision Replay",
      badge: replayErrorState ? "ERROR" : replay?.status || "NOT RUN",
    },
  ];

  const handleRunReplay = async () => {
    if (isExecutingReplay) return;
    setIsExecutingReplay(true);
    setReplayError(null);
    try {
      await executeDecisionReplay(decisionId);
      onRefreshReplay();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Replay execution failed";
      setReplayError(msg);
    } finally {
      setIsExecutingReplay(false);
    }
  };

  return (
    <section className="edos-ws-section" aria-labelledby="trust-heading">
      <div className="edos-ws-section__header">
        <h2 id="trust-heading" className="edos-ws-section__title">
          Section C: Evidence and Decision Trust
        </h2>
        <span className="edos-ws-section__tag">VERIFICATION, PROVENANCE & REPLAY</span>
      </div>

      <div className="edos-ws-trust-container">
        {/* Sub-navigation tabs */}
        <div style={{ marginBottom: "16px" }}>
          <Tabs
            tabs={tabs}
            activeTab={activeTab}
            onChange={(tabId) => setActiveTab(tabId)}
          />
        </div>

        {/* Tab 1: Hard-Constraint Validation */}
        {activeTab === "constraints" && (
          <div className="edos-ws-tab-pane">
            <Card
              title="Constraint Validation Report (Day 21)"
              description="Deterministic hard boundaries evaluated per candidate action before recommendation ranking."
              headerAction={
                onRevalidatePrompt ? (
                  <Button size="sm" variant="outline" onClick={onRevalidatePrompt} disabled={isLoading}>
                    ↻ Re-evaluate Constraints
                  </Button>
                ) : undefined
              }
            >
              {validationStatus === "loading" || isLoading ? (
                <LoadingState label="Loading constraint validation report..." />
              ) : validationError ? (
                <ErrorState
                  title="Constraint Validation Report Failed"
                  message={validationError.message}
                  code={validationError.errorCode || `HTTP_${validationError.statusCode || 500}`}
                  onRetry={onRetryValidation}
                  retryLabel="Retry Validation Load"
                />
              ) : !validation ? (
                <EmptyState
                  title="No Validation Report Recorded"
                  description="No constraint validation report recorded for this decision run."
                  action={
                    onRevalidatePrompt ? (
                      <Button size="sm" variant="primary" onClick={onRevalidatePrompt} style={{ marginTop: "8px" }}>
                        Run Constraint Validation
                      </Button>
                    ) : undefined
                  }
                />
              ) : (
                <>
                  <div className="edos-ws-validation-summary">
                    <div className="edos-ws-summary-pill">
                      <span>Overall Decision Status:</span>
                      <Badge
                        variant={
                          validation.status === "ALL_SATISFIED"
                            ? "success"
                            : validation.status === "SOME_VIOLATED" || validation.status === "ALL_VIOLATED"
                            ? "danger"
                            : "warning"
                        }
                      >
                        {validation.status}
                      </Badge>
                    </div>
                    <div className="edos-ws-summary-pill">
                      <span>Actions Evaluated:</span>
                      <strong>{validation.total_actions_evaluated}</strong>
                    </div>
                    <div className="edos-ws-summary-pill">
                      <span>Invalid Actions:</span>
                      <Badge variant={validation.invalid_action_ids?.length > 0 ? "danger" : "success"}>
                        {validation.invalid_action_ids?.length ?? 0}
                      </Badge>
                    </div>
                  </div>

                  {validation.action_results && validation.action_results.length > 0 ? (
                    <div className="edos-table-container" style={{ marginTop: "16px" }}>
                      <table className="edos-table" aria-label="Action constraint evaluations">
                        <thead>
                          <tr>
                            <th>Action ID</th>
                            <th>Action Type</th>
                            <th>Status</th>
                            <th>Constraints Passed</th>
                            <th>Constraints Failed</th>
                            <th>Validation Notes</th>
                          </tr>
                        </thead>
                        <tbody>
                          {validation.action_results.map((act) => (
                            <tr key={act.action_id}>
                              <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                                {act.action_id}
                              </td>
                              <td>
                                <Badge variant="neutral">{act.action_type}</Badge>
                              </td>
                              <td>
                                <Badge
                                  variant={
                                    act.status === "SATISFIED"
                                      ? "success"
                                      : act.status === "VIOLATED"
                                      ? "danger"
                                      : "warning"
                                  }
                                >
                                  {act.status}
                                </Badge>
                              </td>
                              <td style={{ fontFamily: "var(--font-mono)" }}>
                                {act.constraints_passed ?? 0}
                              </td>
                              <td style={{ fontFamily: "var(--font-mono)" }}>
                                {act.constraints_failed ?? 0}
                              </td>
                              <td style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                                {act.validation_notes && act.validation_notes.length > 0 ? (
                                  <span>
                                    {act.validation_notes.join("; ")}
                                  </span>
                                ) : (
                                  <span style={{ color: "var(--success)" }}>All evaluated constraints passed</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="edos-ws-empty-panel">
                      No candidate actions were evaluated under this validation run.
                    </div>
                  )}
                </>
              )}
            </Card>
          </div>
        )}

        {/* Tab 2: Consolidated Evidence Sheet */}
        {activeTab === "evidence" && (
          <div className="edos-ws-tab-pane">
            <Card
              title="Consolidated Evidence Sheet (Day 22)"
              description="Explicit separation of empirical facts, operational assumptions, and derived mathematical formulas."
            >
              {evidenceStatus === "loading" || isLoading ? (
                <LoadingState label="Loading evidence sheet and assumptions..." />
              ) : evidenceError ? (
                <ErrorState
                  title="Evidence Sheet Retrieval Failed"
                  message={evidenceError.message}
                  code={evidenceError.errorCode || `HTTP_${evidenceError.statusCode || 500}`}
                  onRetry={onRetryEvidence}
                  retryLabel="Retry Evidence Load"
                />
              ) : !evidenceSheet ? (
                <EmptyState
                  title="No Evidence Sheet Compiled"
                  description="No consolidated evidence sheet compiled yet for this decision run."
                />
              ) : (
                (() => {
                  const facts = evidenceSheet.items?.filter((i) => i.evidence_type === "FACT") || [];
                  const calculations = evidenceSheet.items?.filter((i) => i.evidence_type === "CALCULATION") || [];
                  const assumptions = evidenceSheet.assumptions || [];
                  const totalFacts = evidenceSheet.summary?.total_facts ?? facts.length;
                  const totalAssumptions = evidenceSheet.summary?.total_assumptions ?? assumptions.length;
                  const totalCalculations = evidenceSheet.summary?.total_calculations ?? calculations.length;

                  return (
                    <>
                      <div className="edos-ws-grid edos-ws-grid--3col" style={{ marginBottom: "16px" }}>
                        <div className="edos-ws-stat-card">
                          <span className="edos-ws-stat-card__label">Empirical Facts</span>
                          <span className="edos-ws-stat-card__val">{totalFacts}</span>
                          <span className="edos-ws-stat-card__sub">Grounded repository records</span>
                        </div>
                        <div className="edos-ws-stat-card">
                          <span className="edos-ws-stat-card__label">Explicit Assumptions</span>
                          <span className="edos-ws-stat-card__val">{totalAssumptions}</span>
                          <span className="edos-ws-stat-card__sub">Distinguished from facts</span>
                        </div>
                        <div className="edos-ws-stat-card">
                          <span className="edos-ws-stat-card__label">Derived Calculations</span>
                          <span className="edos-ws-stat-card__val">{totalCalculations}</span>
                          <span className="edos-ws-stat-card__sub">Deterministic formulas</span>
                        </div>
                      </div>

                      {/* Facts Section */}
                      <div style={{ marginBottom: "20px" }}>
                        <h5 style={{ marginBottom: "8px", color: "var(--text-primary)" }}>
                          Recorded Facts (Empirical Grounding)
                        </h5>
                        {facts.length > 0 ? (
                          <table className="edos-table">
                            <thead>
                              <tr>
                                <th>Category</th>
                                <th>Fact Description</th>
                                <th>Recorded Value</th>
                                <th>Source Reference</th>
                              </tr>
                            </thead>
                            <tbody>
                              {facts.map((fact) => (
                                <tr key={fact.id}>
                                  <td>
                                    <Badge variant="outline">{fact.category}</Badge>
                                  </td>
                                  <td>{fact.description}</td>
                                  <td style={{ fontFamily: "var(--font-mono)" }}>
                                    {fact.value !== null && fact.value !== undefined ? (
                                      <>
                                        {JSON.stringify(fact.value)}
                                        {fact.unit ? ` ${fact.unit}` : ""}
                                      </>
                                    ) : (
                                      "UNAVAILABLE"
                                    )}
                                  </td>
                                  <td style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                                    {fact.source || "System Database"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                            No specific empirical facts recorded.
                          </p>
                        )}
                      </div>

                  {/* Assumptions Section */}
                  <div>
                    <h5 style={{ marginBottom: "8px", color: "var(--text-primary)" }}>
                      Operational Assumptions (Explicitly Declared)
                    </h5>
                    <div className="edos-ws-assumption-notice">
                      <strong>Assumption Invariant:</strong> Assumptions represent operational modeling
                      hypotheses and are never treated as observed facts.
                    </div>
                    {evidenceSheet.assumptions && evidenceSheet.assumptions.length > 0 ? (
                      <table className="edos-table" style={{ marginTop: "8px" }}>
                        <thead>
                          <tr>
                            <th>Category</th>
                            <th>Assumption Statement</th>
                            <th>Assumed Value</th>
                            <th>Rationale / Source</th>
                          </tr>
                        </thead>
                        <tbody>
                          {evidenceSheet.assumptions.map((asm) => (
                            <tr key={asm.id}>
                              <td>
                                <Badge variant="warning">{asm.category}</Badge>
                              </td>
                              <td>{asm.statement}</td>
                              <td style={{ fontFamily: "var(--font-mono)" }}>
                                {asm.assumed_value !== undefined ? JSON.stringify(asm.assumed_value) : "—"}
                              </td>
                              <td style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                                {asm.rationale || asm.source || "Domain default"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                        No special assumptions declared (standard operational defaults apply).
                      </p>
                    )}
                      </div>
                    </>
                  );
                })()
              )}
            </Card>
          </div>
        )}

        {/* Tab 3: Provenance Lineage */}
        {activeTab === "provenance" && (
          <div className="edos-ws-tab-pane">
            <Card
              title="Provenance Lineage Trace (Day 23)"
              description="Four-stage computational lineage guaranteeing end-to-end auditability: INPUT → RULE → CALCULATION → RESULT."
            >
              {provenanceStatus === "loading" || isLoading ? (
                <LoadingState label="Loading provenance derivation trace..." />
              ) : provenanceError ? (
                <ErrorState
                  title="Provenance Trace Retrieval Failed"
                  message={provenanceError.message}
                  code={provenanceError.errorCode || `HTTP_${provenanceError.statusCode || 500}`}
                  onRetry={onRetryProvenance}
                  retryLabel="Retry Provenance Load"
                />
              ) : !provenance ? (
                <div className="edos-ws-empty-panel">
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                    <Badge variant="warning">HISTORICAL DATA UNAVAILABLE</Badge>
                  </div>
                  <p>Historical provenance trace is incomplete or unavailable for this decision run.</p>
                  <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                    EDOS maintains mathematical auditability and never fabricates missing derivation steps or inputs.
                  </span>
                </div>
              ) : (
                <div className="edos-ws-provenance-view">
                  <div className="edos-ws-provenance-meta">
                    <span>
                      <strong>Trace ID:</strong> <code>{provenance.id}</code>
                    </span>
                    <span>
                      <strong>Status:</strong>{" "}
                      <Badge variant={provenance.status === "SUCCESS" ? "success" : "warning"}>
                        {provenance.status}
                      </Badge>
                    </span>
                    <span>
                      <strong>Captured:</strong>{" "}
                      {new Date(provenance.created_at).toLocaleTimeString()}
                    </span>
                  </div>

                  {/* 4-Stage Visual Pipeline */}
                  <div className="edos-ws-pipeline-track">
                    <div className="edos-ws-stage-box">
                      <span className="edos-ws-stage-box__num">Stage 1</span>
                      <h6>INPUT</h6>
                      <span className="edos-ws-stage-box__count">
                        {provenance.inputs?.length ?? 0} inputs captured
                      </span>
                    </div>

                    <span className="edos-ws-pipeline-arrow" aria-hidden="true">→</span>

                    <div className="edos-ws-stage-box">
                      <span className="edos-ws-stage-box__num">Stage 2</span>
                      <h6>RULE</h6>
                      <span className="edos-ws-stage-box__count">
                        {provenance.rules?.length ?? 0} rules evaluated
                      </span>
                    </div>

                    <span className="edos-ws-pipeline-arrow" aria-hidden="true">→</span>

                    <div className="edos-ws-stage-box">
                      <span className="edos-ws-stage-box__num">Stage 3</span>
                      <h6>CALCULATION</h6>
                      <span className="edos-ws-stage-box__count">
                        {provenance.calculations?.length ?? 0} calculations
                      </span>
                    </div>

                    <span className="edos-ws-pipeline-arrow" aria-hidden="true">→</span>

                    <div className="edos-ws-stage-box edos-ws-stage-box--result">
                      <span className="edos-ws-stage-box__num">Stage 4</span>
                      <h6>RESULT</h6>
                      <span className="edos-ws-stage-box__count">
                        {provenance.results?.length ?? 0} outputs produced
                      </span>
                    </div>
                  </div>

                  {/* Lineage Details */}
                  {provenance.inputs && provenance.inputs.length > 0 && (
                    <div style={{ marginTop: "16px" }}>
                      <h6>Stage 1 Inputs Recorded</h6>
                      <ul className="edos-bullet-list">
                        {provenance.inputs.map((inp, idx) => (
                          <li key={idx}>
                            <strong>{inp.name}</strong> ({inp.input_type}):{" "}
                            <code>{JSON.stringify(inp.value)}</code>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {provenance.calculations && provenance.calculations.length > 0 && (
                    <div style={{ marginTop: "16px" }}>
                      <h6>Stage 3 Mathematical Calculations</h6>
                      <ul className="edos-bullet-list">
                        {provenance.calculations.map((calc, idx) => (
                          <li key={idx}>
                            <strong>{calc.calculation_name}:</strong> <code>{calc.formula}</code> ={" "}
                            <strong>{JSON.stringify(calc.output_value)}</strong>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>
        )}

        {/* Tab 4: Decision Replay */}
        {activeTab === "replay" && (
          <div className="edos-ws-tab-pane">
            <Card
              title="Decision Replay & Reproducibility (Day 24)"
              description="Executes historical re-evaluation against baseline context to verify pure mathematical determinism."
              headerAction={
                <Button
                  size="sm"
                  variant="primary"
                  onClick={handleRunReplay}
                  disabled={isExecutingReplay}
                >
                  {isExecutingReplay ? "Executing Replay..." : "Run Replay Verification"}
                </Button>
              }
            >
              {replayError && (
                <div className="edos-alert edos-alert--danger" role="alert" style={{ marginBottom: "16px" }}>
                  {replayError}
                </div>
              )}

              {replayStatus === "loading" || isLoading ? (
                <LoadingState label="Loading decision replay record..." />
              ) : replayErrorState ? (
                <ErrorState
                  title="Replay Record Retrieval Failed"
                  message={replayErrorState.message}
                  code={replayErrorState.errorCode || `HTTP_${replayErrorState.statusCode || 500}`}
                  onRetry={onRetryReplay}
                  retryLabel="Retry Replay Record"
                />
              ) : !replay ? (
                <EmptyState
                  title="No Replay Verification Record"
                  description="No replay verification has been executed yet for this decision. Click 'Run Replay Verification' above to evaluate mathematical determinism."
                />
              ) : (
                <div className="edos-ws-replay-results">
                  {replay.status === "INCOMPLETE" && (
                    <div className="edos-alert edos-alert--warning" style={{ marginBottom: "16px" }}>
                      <strong>Historical Inputs Incomplete:</strong> Replay execution could not fully complete because past provenance traces or snapshots are partially unavailable.
                      EDOS strictly refused to substitute live context for missing historical data.
                    </div>
                  )}

                  <div className="edos-ws-replay-status-row">
                    <span>Replay Match Status:</span>
                    <Badge
                      variant={
                        replay.status === "MATCHED"
                          ? "success"
                          : replay.status === "DIFFERENT"
                          ? "danger"
                          : "warning"
                      }
                      style={{ fontSize: "0.875rem", padding: "4px 10px" }}
                    >
                      {replay.status}
                    </Badge>
                  </div>

                  <KeyValue
                    columns={2}
                    items={[
                      { label: "Replay Record ID", value: replay.id, monospace: true },
                      {
                        label: "Baseline Recommendation Action",
                        value: replay.original_result?.recommended_action_type || "None",
                        monospace: true,
                      },
                      {
                        label: "Replay Execution Timestamp",
                        value: new Date(replay.created_at).toLocaleString(),
                      },
                      {
                        label: "Differences Detected",
                        value:
                          (replay.comparison?.differences?.length ?? 0) === 0
                            ? "0 (Identical Outputs)"
                            : `${replay.comparison?.differences?.length} differences`,
                      },
                      ...(replay.incomplete_reasons && replay.incomplete_reasons.length > 0
                        ? [
                            {
                              label: "Incomplete Reasons",
                              value: (
                                <span style={{ color: "var(--warning)" }}>
                                  {replay.incomplete_reasons.map((r) => r.code).join(", ")}
                                </span>
                              ),
                            },
                          ]
                        : []),
                    ]}
                  />

                  {/* Field Differences Table if any */}
                  {replay.comparison?.differences && replay.comparison.differences.length > 0 && (
                    <div style={{ marginTop: "16px" }}>
                      <h6>Replay Field Divergences</h6>
                      <table className="edos-table">
                        <thead>
                          <tr>
                            <th>Field Path</th>
                            <th>Original Baseline Value</th>
                            <th>Replay Value</th>
                            <th>Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {replay.comparison.differences.map((fd, i) => (
                            <tr key={i}>
                              <td><code>{fd.field_path}</code></td>
                              <td><code>{JSON.stringify(fd.original_value)}</code></td>
                              <td><code>{JSON.stringify(fd.replayed_value)}</code></td>
                              <td>{fd.difference_description}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>
        )}
      </div>
    </section>
  );
}
