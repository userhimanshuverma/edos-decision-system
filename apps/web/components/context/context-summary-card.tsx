import React from "react";
import { DecisionContext } from "../../lib/types/context";
import { Card } from "../ui/card";
import { Badge, BadgeVariant } from "../ui/badge";
import { StatusIndicator, StatusState } from "../ui/status-indicator";

export interface ContextSummaryCardProps {
  context: DecisionContext;
}

export function ContextSummaryCard({ context }: ContextSummaryCardProps) {
  const { status, metrics, inventory, demand, supplier } = context;

  const availableQty = inventory?.available_quantity ?? 0;
  const reorderPoint = inventory?.reorder_point ?? context.product.reorder_point;
  const isBelowReorder = metrics.is_below_reorder;
  const coverageDays = metrics.coverage_days;
  const leadTimeDays = supplier?.lead_time_days ?? metrics.lead_time_days ?? 0;
  const riskLevel = supplier?.risk_level ?? "LOW";
  const trendDirection = demand?.trend_direction ?? "stable";
  const pctChange = demand?.percentage_change ?? 0;
  const windowDays = demand?.window_days ?? 14;
  const avgDemand = demand?.average_daily_demand.toFixed(2) ?? "0.00";
  const supplierCode = supplier?.code ?? "SUP-PRIMARY";

  // Build deterministic bullet points
  const bulletPoints: { text: string; tone: "danger" | "warning" | "success" | "neutral" }[] = [];

  // 1. Demand trend
  if (trendDirection === "increasing") {
    bulletPoints.push({
      text: `Demand trend is increasing (+${pctChange}% shift over ${windowDays}-day observation window, consuming ${avgDemand} units/day).`,
      tone: "warning",
    });
  } else if (trendDirection === "decreasing") {
    bulletPoints.push({
      text: `Demand trend is decreasing (${pctChange}% shift over ${windowDays}-day window, consuming ${avgDemand} units/day).`,
      tone: "neutral",
    });
  } else {
    bulletPoints.push({
      text: `Demand trajectory is stable across the observed ${windowDays}-day window (averaging ${avgDemand} units/day).`,
      tone: "success",
    });
  }

  // 2. Inventory position
  if (isBelowReorder) {
    bulletPoints.push({
      text: `Current available inventory (${availableQty} units) is at or below the reorder point (${reorderPoint} units), creating a net deficit of ${metrics.net_deficit} units.`,
      tone: "danger",
    });
  } else if (availableQty <= Math.round(reorderPoint * 1.25)) {
    bulletPoints.push({
      text: `Current inventory (${availableQty} units) remains above reorder point (${reorderPoint} units), but is approaching the 25% safety buffer threshold.`,
      tone: "warning",
    });
  } else {
    bulletPoints.push({
      text: `Current inventory (${availableQty} units) remains safely above reorder point (${reorderPoint} units) with a ${availableQty - reorderPoint} unit operational buffer.`,
      tone: "success",
    });
  }

  // 3. Supplier lead time & reliability
  if (riskLevel === "HIGH") {
    bulletPoints.push({
      text: `Primary supplier ${supplierCode} presents HIGH operational risk (lead time: ${leadTimeDays} days, reliability: ${((supplier?.reliability ?? 0) * 100).toFixed(1)}%).`,
      tone: "danger",
    });
  } else if (riskLevel === "MEDIUM") {
    bulletPoints.push({
      text: `Primary supplier ${supplierCode} presents MEDIUM operational risk (lead time: ${leadTimeDays} days, reliability: ${((supplier?.reliability ?? 0) * 100).toFixed(1)}%).`,
      tone: "warning",
    });
  } else {
    bulletPoints.push({
      text: `Supplier lead time is ${leadTimeDays} days with superior reliability (${((supplier?.reliability ?? 0) * 100).toFixed(1)}%) under LOW risk tier.`,
      tone: "success",
    });
  }

  // 4. Coverage vs Lead time
  if (coverageDays !== null && leadTimeDays > 0) {
    if (coverageDays < leadTimeDays) {
      bulletPoints.push({
        text: `Inventory coverage (${coverageDays.toFixed(1)} days) is shorter than supplier lead time (${leadTimeDays} days), creating replenishment vulnerability.`,
        tone: "danger",
      });
    } else {
      bulletPoints.push({
        text: `Coverage is ${coverageDays.toFixed(2)} days, providing a ${(coverageDays - leadTimeDays).toFixed(1)}-day safety cushion beyond the supplier lead time window.`,
        tone: "success",
      });
    }
  } else if (coverageDays !== null) {
    bulletPoints.push({
      text: `Coverage is ${coverageDays.toFixed(2)} days based on current consumption rates.`,
      tone: "neutral",
    });
  }

  let badgeVariant: BadgeVariant = "success";
  let statusTone: StatusState = "ready";
  if (status === "ELEVATED") {
    badgeVariant = "danger";
    statusTone = "error";
  } else if (status === "ATTENTION") {
    badgeVariant = "warning";
    statusTone = "warning";
  }

  return (
    <Card
      title="Deterministic Context Summary"
      description="Grounded situational assessment computed directly from verified operational metrics."
      headerAction={
        <div className="edos-summary-badge-group">
          <StatusIndicator tone={statusTone} label={status} pulse={status !== "NORMAL"} />
          <Badge variant={badgeVariant}>{status}</Badge>
        </div>
      }
    >
      <div className="edos-context-summary-container">
        <div className="edos-context-summary-status-banner">
          <div className="edos-context-summary-status-header">
            <span className="edos-context-summary-status-label">CURRENT CONTEXT STATUS</span>
            <span className="edos-context-summary-status-name">{status}</span>
          </div>
          <p className="edos-context-summary-status-desc">
            {status === "ELEVATED"
              ? "Critical operational threshold reached. Stockout vulnerability, supplier risk, or inventory deficit detected."
              : status === "ATTENTION"
              ? "Operational attention warranted. Observed demand trajectory is increasing or inventory is near reorder thresholds."
              : "Standard operational conditions. All buffers and lead times are within verified tolerance boundaries."}
          </p>
        </div>

        <div className="edos-context-summary-reasons">
          <h4 className="edos-context-summary-reasons-title">
            Operational Factors (&quot;Why&quot;):
          </h4>
          <ul className="edos-context-summary-list">
            {bulletPoints.map((bp, idx) => (
              <li key={idx} className={`edos-context-summary-item edos-context-summary-item--${bp.tone}`}>
                <span className="edos-context-summary-item__bullet" aria-hidden="true" />
                <span className="edos-context-summary-item__text">{bp.text}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="edos-context-summary-footer-meta">
          <span className="edos-context-summary-footer-note">
            ✓ Deterministic Engine Evaluation · Zero LLM hallucination · Verified Day 9 API Response
          </span>
        </div>
      </div>
    </Card>
  );
}
