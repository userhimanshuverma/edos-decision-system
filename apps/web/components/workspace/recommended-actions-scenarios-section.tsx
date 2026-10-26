"use client";

import React, { useState } from "react";
import type {
  CandidateActionRecord,
  RecommendationRecord,
  DecisionScenarioRecord,
  ScenarioComparisonRecord,
  ScenarioOverrides,
} from "../../lib/types/decision";
import { executeDecisionScenario, getDecisionScenarioComparison } from "../../lib/api/decision";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { KeyValue } from "../ui/key-value";

export interface RecommendedActionsScenariosSectionProps {
  decisionId: string;
  candidateActions: CandidateActionRecord[];
  recommendation: RecommendationRecord | null;
  scenarios: DecisionScenarioRecord[];
  onRefreshScenarios: () => void;
  onSeedActionsPrompt?: () => void;
  isLoading?: boolean;
}

export function RecommendedActionsScenariosSection({
  decisionId,
  candidateActions,
  recommendation,
  scenarios,
  onRefreshScenarios,
  onSeedActionsPrompt,
  isLoading = false,
}: RecommendedActionsScenariosSectionProps) {
  // Scenario exploration state
  const [demandFactor, setDemandFactor] = useState<number>(1.2);
  const [leadTimeDays, setLeadTimeDays] = useState<number>(14);
  const [unitCost, setUnitCost] = useState<number>(22.5);
  const [isExecutingScenario, setIsExecutingScenario] = useState<boolean>(false);
  const [scenarioError, setScenarioError] = useState<string | null>(null);

  // Active scenario comparison
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(
    scenarios.length > 0 ? scenarios[0].id : null
  );
  const [comparison, setComparison] = useState<ScenarioComparisonRecord | null>(null);
  const [isLoadingComparison, setIsLoadingComparison] = useState<boolean>(false);

  // Fetch comparison when a scenario is selected
  const handleSelectScenario = async (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    setIsLoadingComparison(true);
    setScenarioError(null);
    try {
      const comp = await getDecisionScenarioComparison(decisionId, scenarioId);
      setComparison(comp);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load comparison";
      setScenarioError(msg);
      setComparison(null);
    } finally {
      setIsLoadingComparison(false);
    }
  };

  const handleRunScenario = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsExecutingScenario(true);
    setScenarioError(null);

    const overrides: ScenarioOverrides = {
      demand: { demand_multiplier: demandFactor },
      lead_time: { lead_time_days: leadTimeDays },
      cost: { unit_cost: unitCost },
    };

    try {
      const newScenario = await executeDecisionScenario(
        decisionId,
        overrides,
        `What-if scenario: Demand x${demandFactor}, Lead time ${leadTimeDays}d, Cost $${unitCost}`
      );
      onRefreshScenarios();
      handleSelectScenario(newScenario.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to execute scenario";
      setScenarioError(msg);
    } finally {
      setIsExecutingScenario(false);
    }
  };

  return (
    <section className="edos-ws-section" aria-labelledby="actions-scenarios-heading">
      <div className="edos-ws-section__header">
        <h2 id="actions-scenarios-heading" className="edos-ws-section__title">
          Section B: Recommended Action and Scenarios
        </h2>
        <span className="edos-ws-section__tag">CANDIDATES & SIMULATION</span>
      </div>

      {/* 1. Candidate Actions Table */}
      <Card
        title="Candidate Actions Evaluated"
        description={`${candidateActions.length} operational actions registered for evaluation against deterministic policy.`}
        headerAction={
          candidateActions.length === 0 && onSeedActionsPrompt ? (
            <Button size="sm" variant="outline" onClick={onSeedActionsPrompt}>
              + Register Default Candidates
            </Button>
          ) : undefined
        }
      >
        {candidateActions.length === 0 ? (
          <div className="edos-ws-empty-panel">
            <p>No candidate actions registered yet for this decision run.</p>
            {onSeedActionsPrompt && (
              <Button size="sm" variant="primary" onClick={onSeedActionsPrompt} style={{ marginTop: "8px" }}>
                Generate Standard Candidates (DO_NOTHING & PLACE_ORDER)
              </Button>
            )}
          </div>
        ) : (
          <div className="edos-table-container">
            <table className="edos-table" aria-label="Candidate actions list">
              <thead>
                <tr>
                  <th>Action ID</th>
                  <th>Action Type</th>
                  <th>Parameters</th>
                  <th>Description</th>
                  <th>Status in Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {candidateActions.map((action) => {
                  const isRecommended =
                    recommendation?.recommended_action_id === action.id ||
                    recommendation?.recommended_action?.id === action.id;
                  return (
                    <tr key={action.id} className={isRecommended ? "edos-table__row--highlight" : ""}>
                      <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{action.id}</td>
                      <td>
                        <Badge variant={isRecommended ? "success" : "neutral"}>
                          {action.action_type || action.type}
                        </Badge>
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>
                        {action.parameters && Object.keys(action.parameters).length > 0
                          ? JSON.stringify(action.parameters)
                          : "None"}
                      </td>
                      <td style={{ color: "var(--text-secondary)" }}>{action.description || "—"}</td>
                      <td>
                        {isRecommended ? (
                          <Badge variant="success">★ RECOMMENDED (RANK 1)</Badge>
                        ) : (
                          <span style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                            Alternative
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 2. Alternative Rankings & Mathematical Derivations */}
      {recommendation?.alternatives && recommendation.alternatives.length > 0 && (
        <Card
          title="Action Alternatives Evaluation & Ranking"
          description="Lexicographic Operational Dominance ranking calculated purely by backend engine."
        >
          <div className="edos-table-container">
            <table className="edos-table" aria-label="Action alternatives ranking">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Action Type</th>
                  <th>Eligible</th>
                  <th>Shortfall Addressed</th>
                  <th>Exposure Delta</th>
                  <th>Effective Lead Time</th>
                  <th>Procurement Cost</th>
                  <th>Selection Rationale</th>
                </tr>
              </thead>
              <tbody>
                {recommendation.alternatives.map((alt) => (
                  <tr key={alt.action_id} className={alt.rank === 1 ? "edos-table__row--highlight" : ""}>
                    <td style={{ fontWeight: 700, textAlign: "center" }}>#{alt.rank}</td>
                    <td>
                      <Badge variant={alt.rank === 1 ? "success" : "neutral"}>
                        {alt.action_type}
                      </Badge>
                    </td>
                    <td>
                      <Badge variant={alt.is_eligible ? "success" : "danger"}>
                        {alt.is_eligible ? "ELIGIBLE" : "INELIGIBLE"}
                      </Badge>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {alt.shortfall_satisfaction_ratio !== null ? `${(alt.shortfall_satisfaction_ratio * 100).toFixed(1)}%` : "—"}{" "}
                      ({alt.shortfall_addressed} units)
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {alt.exposure_index_delta !== null
                        ? alt.exposure_index_delta > 0
                          ? `+${alt.exposure_index_delta.toFixed(2)}`
                          : alt.exposure_index_delta.toFixed(2)
                        : "—"}
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {alt.effective_lead_time_days} days
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {alt.direct_procurement_cost !== null ? `$${alt.direct_procurement_cost.toFixed(2)}` : "—"}
                    </td>
                    <td style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                      {alt.selection_notes?.join(" ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* 3. Scenario Engine Comparison (Isolated What-If Simulation) */}
      <Card
        title="Scenario Engine: What-If Exploration"
        description="Simulate hypothetical parameter shifts. Scenario runs do NOT alter the baseline recommendation or mutate operational decision state."
      >
        <div className="edos-ws-scenario-box">
          <div className="edos-ws-scenario-box__notice">
            <span aria-hidden="true">🛡️</span>
            <div>
              <strong>Isolation Invariant:</strong> Scenarios run through isolated backend evaluation.
              Comparing scenarios allows testing sensitivity without changing the current decision recommendation.
            </div>
          </div>

          {/* Scenario Trigger Form */}
          <form onSubmit={handleRunScenario} className="edos-ws-scenario-form">
            <div className="edos-form-group">
              <label htmlFor="demand-multiplier" className="edos-label">
                Demand Multiplier:
              </label>
              <input
                id="demand-multiplier"
                type="number"
                step="0.05"
                min="0.5"
                max="3.0"
                className="edos-input"
                value={demandFactor}
                onChange={(e) => setDemandFactor(parseFloat(e.target.value) || 1.0)}
                disabled={isExecutingScenario}
              />
              <span className="edos-help-text">Baseline x multiplier (e.g. 1.25 = +25% spike)</span>
            </div>

            <div className="edos-form-group">
              <label htmlFor="lead-time-override" className="edos-label">
                Lead Time (days):
              </label>
              <input
                id="lead-time-override"
                type="number"
                step="1"
                min="1"
                max="60"
                className="edos-input"
                value={leadTimeDays}
                onChange={(e) => setLeadTimeDays(parseInt(e.target.value, 10) || 10)}
                disabled={isExecutingScenario}
              />
              <span className="edos-help-text">Simulated supplier delivery window</span>
            </div>

            <div className="edos-form-group">
              <label htmlFor="unit-cost-override" className="edos-label">
                Unit Cost ($):
              </label>
              <input
                id="unit-cost-override"
                type="number"
                step="0.5"
                min="1"
                max="500"
                className="edos-input"
                value={unitCost}
                onChange={(e) => setUnitCost(parseFloat(e.target.value) || 10.0)}
                disabled={isExecutingScenario}
              />
              <span className="edos-help-text">Procurement price override</span>
            </div>

            <div className="edos-form-group edos-form-group--submit">
              <Button type="submit" variant="primary" disabled={isExecutingScenario}>
                {isExecutingScenario ? "Simulating..." : "Execute Scenario"}
              </Button>
            </div>
          </form>

          {scenarioError && (
            <div className="edos-alert edos-alert--danger" role="alert">
              {scenarioError}
            </div>
          )}

          {/* Available Scenarios Selector */}
          {scenarios.length > 0 && (
            <div className="edos-ws-scenario-list">
              <label htmlFor="scenario-select" className="edos-label">
                Recorded Scenarios ({scenarios.length}):
              </label>
              <div className="edos-ws-scenario-chips">
                {scenarios.map((sc) => (
                  <button
                    key={sc.id}
                    type="button"
                    className={`edos-chip ${selectedScenarioId === sc.id ? "edos-chip--active" : ""}`}
                    onClick={() => handleSelectScenario(sc.id)}
                  >
                    <span>{sc.id}</span>
                    <Badge variant={sc.status === "COMPLETED" ? "neutral" : "warning"}>
                      {sc.status}
                    </Badge>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Baseline vs Scenario Comparison Display */}
          {isLoadingComparison && (
            <div className="edos-skeleton-text" style={{ padding: "16px" }}>
              Loading comparison data...
            </div>
          )}

          {comparison && !isLoadingComparison && (
            <div className="edos-ws-comparison-panel">
              <div className="edos-ws-comparison-header">
                <h4>
                  Baseline vs Scenario Comparison ({selectedScenarioId})
                </h4>
                <Badge variant={comparison.recommendation_changed ? "warning" : "success"}>
                  {comparison.recommendation_changed ? "RECOMMENDATION CHANGED" : "RECOMMENDATION UNCHANGED"}
                </Badge>
              </div>

              {comparison.summary && (
                <div style={{ marginTop: "12px", padding: "12px", background: "var(--bg-secondary)", borderRadius: "var(--radius-sm)", fontSize: "0.875rem", borderLeft: "3px solid var(--accent-primary)" }}>
                  <strong>Comparison Summary:</strong> {comparison.summary}
                </div>
              )}

              {/* Side-by-side Snapshot Cards */}
              <div className="edos-ws-grid edos-ws-grid--2col" style={{ marginTop: "16px" }}>
                <div className="edos-ws-comp-card edos-ws-comp-card--baseline">
                  <h5>Baseline Decision (Original)</h5>
                  <KeyValue
                    columns={1}
                    items={[
                      {
                        label: "Selected Action Type",
                        value: comparison.baseline_action_type || "None",
                        monospace: true,
                      },
                      {
                        label: "Validation Status",
                        value: comparison.baseline_validation_status || "—",
                      },
                      {
                        label: "Recommendation ID",
                        value: comparison.baseline_recommendation_id || "—",
                        monospace: true,
                      },
                    ]}
                  />
                </div>

                <div className="edos-ws-comp-card edos-ws-comp-card--scenario">
                  <h5>Scenario Snapshot (Simulated)</h5>
                  <KeyValue
                    columns={1}
                    items={[
                      {
                        label: "Selected Action Type",
                        value: comparison.scenario_action_type || "None",
                        monospace: true,
                      },
                      {
                        label: "Validation Status",
                        value: comparison.scenario_validation_status || "—",
                      },
                      {
                        label: "Recommendation ID",
                        value: comparison.scenario_recommendation_id || "—",
                        monospace: true,
                      },
                    ]}
                  />
                </div>
              </div>

              {/* Metric Deltas Table */}
              <div className="edos-ws-deltas-table" style={{ marginTop: "16px" }}>
                <h6>Backend Evaluated Metric Deltas</h6>
                <table className="edos-table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Baseline Value</th>
                      <th>Scenario Value</th>
                      <th>Delta / Shift</th>
                      <th>Unit</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ fontWeight: 600 }}>Replenishment Quantity</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>
                        {comparison.replenishment_quantity?.baseline_value !== null ? String(comparison.replenishment_quantity?.baseline_value) : "—"}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>
                        {comparison.replenishment_quantity?.scenario_value !== null ? String(comparison.replenishment_quantity?.scenario_value) : "—"}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                        {comparison.replenishment_quantity?.difference !== null ? String(comparison.replenishment_quantity?.difference) : "—"}
                      </td>
                      <td>{comparison.replenishment_quantity?.unit || "units"}</td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 600 }}>Direct Procurement Cost</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>
                        {comparison.procurement_cost?.baseline_value !== null ? `$${comparison.procurement_cost?.baseline_value}` : "—"}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>
                        {comparison.procurement_cost?.scenario_value !== null ? `$${comparison.procurement_cost?.scenario_value}` : "—"}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                        {comparison.procurement_cost?.difference !== null ? `$${comparison.procurement_cost?.difference}` : "—"}
                      </td>
                      <td>{comparison.procurement_cost?.unit || "USD"}</td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 600 }}>Lead Time Exposure</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>
                        {comparison.lead_time_exposure?.baseline_value !== null ? String(comparison.lead_time_exposure?.baseline_value) : "—"}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>
                        {comparison.lead_time_exposure?.scenario_value !== null ? String(comparison.lead_time_exposure?.scenario_value) : "—"}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                        {comparison.lead_time_exposure?.difference !== null ? String(comparison.lead_time_exposure?.difference) : "—"}
                      </td>
                      <td>{comparison.lead_time_exposure?.unit || "exposure"}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Constraint Status Changes */}
              {comparison.validation_status_changed && (
                <div style={{ marginTop: "16px" }}>
                  <Badge variant="warning">Validation Status Changed</Badge>
                  {comparison.newly_violated_constraints?.length > 0 && (
                    <div style={{ marginTop: "8px" }}>
                      <strong style={{ color: "var(--danger)" }}>Newly Violated:</strong>{" "}
                      {comparison.newly_violated_constraints.join(", ")}
                    </div>
                  )}
                  {comparison.newly_satisfied_constraints?.length > 0 && (
                    <div style={{ marginTop: "8px" }}>
                      <strong style={{ color: "var(--success)" }}>Newly Satisfied:</strong>{" "}
                      {comparison.newly_satisfied_constraints.join(", ")}
                    </div>
                  )}
                </div>
              )}

              {/* Granular Field Differences */}
              {comparison.differences && comparison.differences.length > 0 && (
                <div style={{ marginTop: "16px" }}>
                  <h6>Field Differences Identified ({comparison.differences.length})</h6>
                  <ul className="edos-bullet-list">
                    {comparison.differences.map((fd, i) => (
                      <li key={i}>
                        <code>{fd.field_path}</code>: Baseline{" "}
                        <strong>{JSON.stringify(fd.baseline_value)}</strong> → Scenario{" "}
                        <strong>{JSON.stringify(fd.scenario_value)}</strong> ({fd.difference_description})
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </Card>
    </section>
  );
}
