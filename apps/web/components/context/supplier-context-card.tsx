import React from "react";
import { DecisionContext } from "../../lib/types/context";
import { Card } from "../ui/card";
import { Badge, BadgeVariant } from "../ui/badge";
import { KeyValue, KeyValueItem } from "../ui/key-value";

export interface SupplierContextCardProps {
  context: DecisionContext;
}

export function SupplierContextCard({ context }: SupplierContextCardProps) {
  const { supplier, metrics } = context;

  if (!supplier) {
    return (
      <Card
        title="Supplier Operational Intelligence"
        description="Fulfillment parameters and deterministic supplier risk classification."
      >
        <div className="edos-demand-empty">
          <p>No primary supplier configured for this product category.</p>
        </div>
      </Card>
    );
  }

  const { name, code, lead_time_days, reliability, active, risk_level } = supplier;
  const coverageDays = metrics.coverage_days;

  const riskBadgeVariant: BadgeVariant =
    risk_level === "HIGH" ? "danger" : risk_level === "MEDIUM" ? "warning" : "success";

  const leadTimeBuffer =
    coverageDays !== null ? (coverageDays - lead_time_days).toFixed(1) : null;
  const isCoverageShorterThanLeadTime =
    coverageDays !== null && coverageDays < lead_time_days;

  const kvItems: KeyValueItem[] = [
    {
      label: "Supplier Name & Code",
      value: name,
      badge: <Badge variant="outline">{code}</Badge>,
      description: "Designated primary operational vendor for this SKU.",
    },
    {
      label: "Fulfillment Lead Time",
      value: `${lead_time_days} days`,
      badge: (
        <Badge variant={lead_time_days > 14 ? "warning" : "neutral"}>
          {lead_time_days}d SLA
        </Badge>
      ),
      description: "Elapsed duration from purchase order placement to dock arrival.",
      monospace: true,
    },
    {
      label: "Historical Reliability",
      value: `${(reliability * 100).toFixed(1)}%`,
      badge: (
        <Badge variant={reliability >= 0.95 ? "success" : reliability >= 0.85 ? "warning" : "danger"}>
          {reliability >= 0.95 ? "SUPERIOR" : reliability >= 0.85 ? "ACCEPTABLE" : "AT RISK"}
        </Badge>
      ),
      description: "Historical on-time in-full (OTIF) fulfillment rate.",
      monospace: true,
    },
    {
      label: "Operational Risk Tier",
      value: `Risk Tier: ${risk_level}`,
      badge: <Badge variant={riskBadgeVariant}>{risk_level}</Badge>,
      description: "Deterministic operational risk evaluated by Day 8 Supplier Engine.",
    },
    {
      label: "Vendor Status",
      value: active ? "Active & Eligible" : "Inactive / Disqualified",
      badge: <Badge variant={active ? "success" : "danger"}>{active ? "ACTIVE" : "INACTIVE"}</Badge>,
      description: "Procurement eligibility for replenishment orders.",
    },
    {
      label: "Coverage vs Lead Time Buffer",
      value:
        leadTimeBuffer !== null
          ? isCoverageShorterThanLeadTime
            ? `Deficit: ${Math.abs(Number(leadTimeBuffer))} days short`
            : `Surplus: +${leadTimeBuffer} days buffer`
          : "N/A",
      badge: (
        <Badge variant={isCoverageShorterThanLeadTime ? "danger" : "success"}>
          {isCoverageShorterThanLeadTime ? "DEFICIT BUFFER" : "SAFE BUFFER"}
        </Badge>
      ),
      description:
        "Comparison of available coverage against expected supply delivery time.",
      monospace: true,
    },
  ];

  return (
    <Card
      title="Supplier Operational Intelligence"
      description="Deterministic supplier parameters, fulfillment lead times, and upstream reliability."
      headerAction={<Badge variant={riskBadgeVariant}>Risk: {risk_level}</Badge>}
    >
      <KeyValue items={kvItems} columns={2} />

      {isCoverageShorterThanLeadTime && (
        <div className="edos-warning-banner" role="alert">
          <span className="edos-warning-banner__icon" aria-hidden="true">
            ⚠
          </span>
          <span className="edos-warning-banner__text">
            <strong>Supply Lead Time Alert:</strong> Standard fulfillment takes{" "}
            {lead_time_days} days, while current stock coverage is only{" "}
            {coverageDays?.toFixed(1)} days.
          </span>
        </div>
      )}
    </Card>
  );
}
