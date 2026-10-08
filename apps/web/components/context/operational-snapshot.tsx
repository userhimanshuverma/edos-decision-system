import React from "react";
import { DecisionContext } from "../../lib/types/context";
import { Metric } from "../ui/metric";
import { Badge, BadgeVariant } from "../ui/badge";

export interface OperationalSnapshotProps {
  context: DecisionContext;
}

export function OperationalSnapshot({ context }: OperationalSnapshotProps) {
  const { inventory, demand, supplier, metrics } = context;

  // Inventory Pillar calculations
  const availableQty = inventory?.available_quantity ?? 0;
  const onHandQty = inventory?.quantity_on_hand ?? 0;
  const reservedQty = inventory?.quantity_reserved ?? 0;
  const reorderPoint = inventory?.reorder_point ?? context.product.reorder_point;
  const isBelowReorder = metrics.is_below_reorder;

  // Demand Pillar calculations
  const avgDemand = demand ? demand.average_daily_demand.toFixed(2) : "0.00";
  const trendDirection = demand?.trend_direction ?? "stable";
  const pctChange = demand ? demand.percentage_change : 0;
  const windowDays = demand?.window_days ?? 0;
  const totalDemand = demand?.total_demand ?? 0;

  // Supplier Pillar calculations
  const supplierName = supplier?.name ?? "Unassigned Supplier";
  const supplierCode = supplier?.code ?? "—";
  const leadTime = supplier?.lead_time_days ?? metrics.lead_time_days ?? 0;
  const reliabilityPct = supplier ? (supplier.reliability * 100).toFixed(1) : "—";
  const riskLevel = supplier?.risk_level ?? "LOW";

  const supplierRiskBadgeVariant: BadgeVariant =
    riskLevel === "HIGH" ? "danger" : riskLevel === "MEDIUM" ? "warning" : "success";

  const trendBadgeVariant: BadgeVariant =
    trendDirection === "increasing"
      ? "warning"
      : trendDirection === "decreasing"
      ? "info"
      : "neutral";

  return (
    <section className="edos-snapshot-section" aria-label="Operational Situation Snapshot">
      <div className="edos-section__header">
        <h2 className="edos-section__title">Operational Snapshot</h2>
        <span className="edos-section__tag">FOUR OPERATIONAL DIMENSIONS</span>
      </div>

      <div className="edos-snapshot-grid">
        {/* Pillar 1: Inventory Position */}
        <Metric
          label="Available Inventory"
          value={
            <div className="edos-snapshot-metric-val">
              <span>{availableQty.toLocaleString()}</span>
              <span className="edos-snapshot-metric-unit">units</span>
            </div>
          }
          badge={isBelowReorder ? "Below Reorder" : "Buffer Intact"}
          badgeVariant={isBelowReorder ? "danger" : "success"}
          note={
            <div className="edos-snapshot-note-list">
              <span className="edos-snapshot-note-item">
                <strong>On Hand:</strong> {onHandQty.toLocaleString()}
              </span>
              <span className="edos-snapshot-note-sep">•</span>
              <span className="edos-snapshot-note-item">
                <strong>Reserved:</strong> {reservedQty.toLocaleString()}
              </span>
              <span className="edos-snapshot-note-sep">•</span>
              <span className="edos-snapshot-note-item">
                <strong>Reorder Point:</strong> {reorderPoint.toLocaleString()}
              </span>
            </div>
          }
        />

        {/* Pillar 2: Demand Velocity */}
        <Metric
          label="Demand Velocity"
          value={
            <div className="edos-snapshot-metric-val">
              <span>{avgDemand}</span>
              <span className="edos-snapshot-metric-unit">units / day</span>
            </div>
          }
          badge={
            <Badge variant={trendBadgeVariant}>
              {trendDirection === "increasing" ? "↑" : trendDirection === "decreasing" ? "↓" : "→"}{" "}
              {trendDirection.toUpperCase()} ({pctChange > 0 ? `+${pctChange}%` : `${pctChange}%`})
            </Badge>
          }
          note={
            <div className="edos-snapshot-note-list">
              <span className="edos-snapshot-note-item">
                <strong>Window:</strong> {windowDays} days observed
              </span>
              <span className="edos-snapshot-note-sep">•</span>
              <span className="edos-snapshot-note-item">
                <strong>Total Consumed:</strong> {totalDemand.toLocaleString()} units
              </span>
            </div>
          }
        />

        {/* Pillar 3: Supplier Lead Time & Risk */}
        <Metric
          label="Supply Fulfillment"
          value={
            <div className="edos-snapshot-metric-val">
              <span>{leadTime}</span>
              <span className="edos-snapshot-metric-unit">days lead time</span>
            </div>
          }
          badge={<Badge variant={supplierRiskBadgeVariant}>RISK: {riskLevel}</Badge>}
          note={
            <div className="edos-snapshot-note-list">
              <span className="edos-snapshot-note-item" title={supplierName}>
                <strong>Supplier:</strong> {supplierCode} ({supplierName})
              </span>
              <span className="edos-snapshot-note-sep">•</span>
              <span className="edos-snapshot-note-item">
                <strong>Reliability:</strong> {reliabilityPct}%
              </span>
            </div>
          }
        />

        {/* Pillar 4: Inventory Coverage Ratio */}
        <Metric
          label="Coverage Window"
          value={
            <div className="edos-snapshot-metric-val">
              <span>{metrics.coverage_days !== null ? metrics.coverage_days.toFixed(1) : "—"}</span>
              <span className="edos-snapshot-metric-unit">days coverage</span>
            </div>
          }
          badge={
            metrics.coverage_days !== null && metrics.lead_time_days !== null && metrics.coverage_days < metrics.lead_time_days ? (
              <Badge variant="danger">Coverage &lt; Lead Time</Badge>
            ) : (
              <Badge variant="neutral">Descriptive Ratio</Badge>
            )
          }
          note={
            <div className="edos-snapshot-note-list">
              <span className="edos-snapshot-note-item">
                <strong>Net Deficit:</strong> {metrics.net_deficit} units
              </span>
              <span className="edos-snapshot-note-sep">•</span>
              <span className="edos-snapshot-note-item">
                <strong>Buffer vs Lead Time:</strong>{" "}
                {metrics.coverage_days !== null && leadTime > 0
                  ? `${(metrics.coverage_days - leadTime).toFixed(1)}d buffer`
                  : "N/A"}
              </span>
            </div>
          }
        />
      </div>
    </section>
  );
}
