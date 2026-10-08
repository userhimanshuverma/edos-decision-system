import React from "react";
import { DecisionContext } from "../../lib/types/context";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { KeyValue, KeyValueItem } from "../ui/key-value";

export interface InventoryPositionCardProps {
  context: DecisionContext;
}

export function InventoryPositionCard({ context }: InventoryPositionCardProps) {
  const { inventory, metrics, product } = context;

  const onHand = inventory?.quantity_on_hand ?? 0;
  const reserved = inventory?.quantity_reserved ?? 0;
  const available = inventory?.available_quantity ?? 0;
  const reorderPoint = inventory?.reorder_point ?? product.reorder_point;
  const netDeficit = metrics.net_deficit;
  const isBelowReorder = metrics.is_below_reorder;
  const coverageDays = metrics.coverage_days;
  const updatedAt = inventory?.updated_at
    ? new Date(inventory.updated_at).toLocaleString("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Verified Synced";

  // Visual allocation calculations
  const totalPhysical = Math.max(onHand, 1);
  const availablePct = Math.round((available / totalPhysical) * 100);
  const reservedPct = Math.round((reserved / totalPhysical) * 100);
  const reorderMarkerPct = Math.min(100, Math.round((reorderPoint / totalPhysical) * 100));

  const kvItems: KeyValueItem[] = [
    {
      label: "Physical On Hand",
      value: `${onHand.toLocaleString()} units`,
      description: "Total physical inventory physically present in facility bins.",
      monospace: true,
    },
    {
      label: "Reserved Stock",
      value: `${reserved.toLocaleString()} units`,
      description: "Allocated to in-flight orders or outbound logistics.",
      monospace: true,
    },
    {
      label: "Available for Allocation",
      value: `${available.toLocaleString()} units`,
      description: "Unallocated units currently free for order commitments.",
      badge: (
        <Badge variant={isBelowReorder ? "danger" : "success"}>
          {isBelowReorder ? "DEFICIT" : "HEALTHY"}
        </Badge>
      ),
      monospace: true,
    },
    {
      label: "Reorder Threshold",
      value: `${reorderPoint.toLocaleString()} units`,
      description: "Predefined operational safety threshold triggering reorder.",
      monospace: true,
    },
    {
      label: "Reorder Position Status",
      value: isBelowReorder ? "Below Reorder Point" : "Above Reorder Point",
      description: isBelowReorder
        ? `Deficit of ${netDeficit} units below threshold.`
        : `Safe buffer of ${available - reorderPoint} units above threshold.`,
      badge: (
        <Badge variant={isBelowReorder ? "danger" : "success"}>
          {isBelowReorder ? `-${netDeficit} Units` : `+${available - reorderPoint} Units`}
        </Badge>
      ),
    },
    {
      label: "Coverage Days (Descriptive)",
      value: coverageDays !== null ? `${coverageDays.toFixed(2)} days` : "Indefinite (0 demand)",
      description: "Ratio: Available units ÷ average daily consumption.",
      badge: (
        <Badge variant={coverageDays !== null && coverageDays < (metrics.lead_time_days ?? 0) ? "danger" : "neutral"}>
          {coverageDays !== null ? `${coverageDays.toFixed(1)}d` : "N/A"}
        </Badge>
      ),
      monospace: true,
    },
  ];

  return (
    <Card
      title="Inventory Position & Allocation"
      description="Observed warehouse stock levels, allocation breakdown, and reorder threshold position."
      headerAction={
        <span className="edos-card-meta-tag">
          Updated: {updatedAt}
        </span>
      }
    >
      {/* Visual Allocation Bar */}
      <div className="edos-inventory-bar-container" aria-label="Inventory visual allocation bar">
        <div className="edos-inventory-bar-header">
          <span className="edos-inventory-bar-title">PHYSICAL INVENTORY ALLOCATION</span>
          <span className="edos-inventory-bar-legend">
            <span className="edos-legend-dot edos-legend-dot--available" /> Available ({availablePct}%)
            <span className="edos-legend-dot edos-legend-dot--reserved" style={{ marginLeft: 12 }} /> Reserved ({reservedPct}%)
            <span className="edos-legend-dot edos-legend-dot--reorder" style={{ marginLeft: 12 }} /> Reorder Threshold ({reorderPoint})
          </span>
        </div>

        <div className="edos-inventory-progress-track">
          <div
            className="edos-inventory-progress-segment edos-inventory-progress-segment--available"
            style={{ width: `${availablePct}%` }}
            title={`Available: ${available} units (${availablePct}%)`}
          />
          <div
            className="edos-inventory-progress-segment edos-inventory-progress-segment--reserved"
            style={{ width: `${reservedPct}%` }}
            title={`Reserved: ${reserved} units (${reservedPct}%)`}
          />
          <div
            className="edos-inventory-reorder-marker"
            style={{ left: `${reorderMarkerPct}%` }}
            title={`Reorder Point: ${reorderPoint} units`}
          >
            <span className="edos-inventory-reorder-tag">Reorder: {reorderPoint}</span>
          </div>
        </div>
      </div>

      {/* Structured KeyValue Grid */}
      <KeyValue items={kvItems} columns={2} className="edos-inventory-kv-grid" />

      {/* Contextual Disclaimer */}
      <div className="edos-context-callout">
        <div className="edos-context-callout__icon" aria-hidden="true">
          ℹ
        </div>
        <div className="edos-context-callout__body">
          <span className="edos-context-callout__title">Descriptive Operational Context</span>
          <p className="edos-context-callout__text">
            Coverage is computed strictly as <code>Available ({available}) ÷ Average Daily Demand ({context.demand?.average_daily_demand.toFixed(2) ?? 0}) = {coverageDays !== null ? `${coverageDays.toFixed(2)} days` : "N/A"}</code>.
            This is an observed historical ratio, not a predictive stockout probability or stochastic model.
          </p>
        </div>
      </div>
    </Card>
  );
}
