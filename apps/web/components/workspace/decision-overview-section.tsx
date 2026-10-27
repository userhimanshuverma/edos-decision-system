"use client";

import React from "react";
import type {
  DecisionRecord,
  RecommendationRecord,
  SectionLoadStatus,
  SectionErrorState,
} from "../../lib/types/decision";
import type { DecisionContext } from "../../lib/types/context";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Metric } from "../ui/metric";
import { KeyValue } from "../ui/key-value";
import { ErrorState } from "../ui/error-state";
import { Button } from "../ui/button";

export interface DecisionOverviewSectionProps {
  decision: DecisionRecord;
  context: DecisionContext | null;
  contextStatus?: SectionLoadStatus;
  contextError?: SectionErrorState | null;
  onRetryContext?: () => void;
  recommendation: RecommendationRecord | null;
  recommendationStatus?: SectionLoadStatus;
  recommendationError?: SectionErrorState | null;
  onRetryRecommendation?: () => void;
  isLoadingContext?: boolean;
}

export function DecisionOverviewSection({
  decision,
  context,
  contextStatus = "idle",
  contextError = null,
  onRetryContext,
  recommendation,
  recommendationStatus = "idle",
  recommendationError = null,
  onRetryRecommendation,
  isLoadingContext = false,
}: DecisionOverviewSectionProps) {
  const isContextLoading = isLoadingContext || contextStatus === "loading";
  const hasContextError = contextStatus === "error" || Boolean(contextError);

  const inv = context?.inventory;
  const dem = context?.demand;
  const sup = context?.supplier;
  const met = context?.metrics;

  const recAction = recommendation?.recommended_action;
  const recActionType = recommendation?.recommended_action_type || recAction?.action_type || "NONE";
  const recParams = recAction?.parameters as Record<string, unknown> | undefined;

  return (
    <section className="edos-ws-section" aria-labelledby="overview-heading">
      <div className="edos-ws-section__header">
        <h2 id="overview-heading" className="edos-ws-section__title">
          Section A: Decision Overview
        </h2>
        <span className="edos-ws-section__tag">OPERATIONAL CONTEXT & STATE</span>
      </div>

      {/* Hero Recommendation Summary Banner */}
      <div className="edos-ws-hero-card">
        <div className="edos-ws-hero-card__main">
          <div className="edos-ws-hero-card__badge-row">
            <span className="edos-ws-hero-card__label">Current Engine Recommendation</span>
            <Badge
              variant={
                recommendationError
                  ? "danger"
                  : recommendation?.status === "RECOMMENDED"
                  ? "success"
                  : recommendation?.status === "NO_ACTION_REQUIRED"
                  ? "neutral"
                  : recommendationStatus === "loading"
                  ? "outline"
                  : "warning"
              }
            >
              {recommendationError
                ? "CALCULATION ERROR"
                : recommendation
                ? recommendation.status
                : recommendationStatus === "loading"
                ? "CALCULATING"
                : "PENDING"}
            </Badge>
          </div>

          <div className="edos-ws-hero-card__action">
            {recommendationError ? (
              <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                <span className="edos-ws-hero-card__pending" style={{ color: "var(--danger-foreground, #f87171)" }}>
                  Failed to compute recommendation: {recommendationError.message}
                </span>
                {onRetryRecommendation && (
                  <Button variant="outline" size="sm" onClick={onRetryRecommendation}>
                    Retry Calculation
                  </Button>
                )}
              </div>
            ) : recommendation ? (
              <>
                <span className="edos-ws-hero-card__action-type">{recActionType}</span>
                {recParams && "quantity" in recParams && (
                  <span className="edos-ws-hero-card__action-qty">
                    Order Quantity: <strong>{String(recParams.quantity)} units</strong>
                  </span>
                )}
                {recParams && "supplier_id" in recParams && (
                  <span className="edos-ws-hero-card__action-sup">
                    Supplier: <strong>{String(recParams.supplier_id)}</strong>
                  </span>
                )}
              </>
            ) : (
              <span className="edos-ws-hero-card__pending">
                {recommendationStatus === "loading"
                  ? "Recommendation calculation in progress..."
                  : "No recommendation computed yet. Add and evaluate candidate actions to generate a recommendation."}
              </span>
            )}
          </div>

          <p className="edos-ws-hero-card__rationale">
            {recommendationError
              ? `Operational error occurred: ${recommendationError.errorCode || "ENGINE_ERROR"}. Core decision engine remains deterministic; retry calculation when ready.`
              : recommendation?.selection_rationale ||
                "Synthesizing operational context and evaluating candidate actions against inventory policy."}
          </p>

          <div className="edos-ws-hero-card__meta">
            <span>
              <strong>Selection Rule:</strong>{" "}
              {recommendation?.selection_rule || "Lexicographic Operational Dominance"}
            </span>
            <span>
              <strong>Tie-Broken:</strong> {recommendation?.tie_broken ? "Yes" : "No"}
            </span>
            <span>
              <strong>Evaluated Actions:</strong>{" "}
              {recommendation?.total_actions_evaluated ?? "—"}
            </span>
          </div>
        </div>
      </div>

      {hasContextError && contextError && (
        <div style={{ marginBottom: "16px" }}>
          <ErrorState
            title="Operational Context Retrieval Error"
            message={contextError.message}
            code={contextError.errorCode || `HTTP_${contextError.statusCode || 500}`}
            onRetry={onRetryContext}
            retryLabel="Retry Context Load"
          />
        </div>
      )}

      {/* Context Pillars Grid: Inventory, Demand, Supplier */}
      <div className="edos-ws-grid edos-ws-grid--3col">
        {/* Card 1: Inventory Position */}
        <Card
          title="Inventory Position"
          description={context ? `${context.product.sku} @ ${context.warehouse.code}` : "Loading inventory..."}
        >
          {isLoadingContext || !inv ? (
            <div className="edos-skeleton-text">Loading inventory position...</div>
          ) : (
            <>
              <div className="edos-ws-metric-strip">
                <Metric
                  label="Available Stock"
                  value={`${inv.available_quantity} units`}
                  note={`On hand: ${inv.quantity_on_hand} | Reserved: ${inv.quantity_reserved}`}
                  badgeVariant={inv.available_quantity <= inv.reorder_point ? "warning" : "success"}
                />
              </div>
              <KeyValue
                columns={1}
                items={[
                  { label: "Reorder Point", value: `${inv.reorder_point} units`, monospace: true },
                  {
                    label: "Reorder Status",
                    value:
                      inv.available_quantity <= inv.reorder_point ? (
                        <Badge variant="warning">BELOW REORDER POINT</Badge>
                      ) : (
                        <Badge variant="success">ADEQUATE</Badge>
                      ),
                  },
                  {
                    label: "Warehouse Capacity",
                    value: context?.warehouse.capacity ? `${context.warehouse.capacity} units` : "—",
                    monospace: true,
                  },
                  {
                    label: "Unit Cost",
                    value: context?.product.unit_cost ? `$${context.product.unit_cost.toFixed(2)}` : "—",
                    monospace: true,
                  },
                ]}
              />
            </>
          )}
        </Card>

        {/* Card 2: Demand Trajectory */}
        <Card
          title="Observed Demand"
          description={dem ? `${dem.window_days}-day historical observation window` : "Loading demand..."}
        >
          {isLoadingContext || !dem ? (
            <div className="edos-skeleton-text">Loading demand behavior...</div>
          ) : (
            <>
              <div className="edos-ws-metric-strip">
                <Metric
                  label="Daily Average"
                  value={`${dem.average_daily_demand.toFixed(1)} u/day`}
                  note={`Trend: ${dem.trend_direction.toUpperCase()}`}
                  badge={dem.trend_direction}
                  badgeVariant={dem.trend_direction === "increasing" ? "warning" : "neutral"}
                />
              </div>
              <KeyValue
                columns={1}
                items={[
                  {
                    label: "Stock Coverage",
                    value:
                      met?.coverage_days !== null && met?.coverage_days !== undefined
                        ? `${met.coverage_days.toFixed(1)} days`
                        : "—",
                    monospace: true,
                  },
                  {
                    label: "Trend Direction",
                    value: <Badge variant="outline">{dem.trend_direction}</Badge>,
                  },
                  {
                    label: "Total Window Volume",
                    value: `${dem.history.reduce((acc, h) => acc + h.quantity, 0)} units`,
                    monospace: true,
                  },
                  {
                    label: "Net Deficit",
                    value: met?.net_deficit ? `${met.net_deficit} units` : "0 units",
                    monospace: true,
                  },
                ]}
              />
            </>
          )}
        </Card>

        {/* Card 3: Upstream Supplier */}
        <Card
          title="Upstream Supplier"
          description={sup ? `${sup.name} (${sup.code})` : "Loading supplier..."}
        >
          {isLoadingContext || !sup ? (
            <div className="edos-skeleton-text">Loading supplier parameters...</div>
          ) : (
            <>
              <div className="edos-ws-metric-strip">
                <Metric
                  label="Lead Time"
                  value={`${sup.lead_time_days} days`}
                  note={`Reliability: ${(sup.reliability * 100).toFixed(0)}%`}
                  badge={`Risk: ${sup.risk_level}`}
                  badgeVariant={sup.risk_level === "LOW" ? "success" : "warning"}
                />
              </div>
              <KeyValue
                columns={1}
                items={[
                  { label: "Supplier Code", value: sup.code, monospace: true },
                  {
                    label: "Risk Classification",
                    value: (
                      <Badge variant={sup.risk_level === "LOW" ? "success" : "warning"}>
                        {sup.risk_level}
                      </Badge>
                    ),
                  },
                  {
                    label: "Reliability Score",
                    value: `${(sup.reliability * 100).toFixed(1)}%`,
                    monospace: true,
                  },
                  {
                    label: "Lead Time Demand",
                    value: `${(dem ? dem.average_daily_demand * sup.lead_time_days : 0).toFixed(0)} units`,
                    monospace: true,
                  },
                ]}
              />
            </>
          )}
        </Card>
      </div>
    </section>
  );
}
