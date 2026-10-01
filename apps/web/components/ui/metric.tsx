import React from "react";
import { Badge } from "./badge";

export interface MetricProps {
  label: string;
  value: React.ReactNode;
  note?: React.ReactNode;
  badge?: React.ReactNode;
  badgeVariant?: "default" | "neutral" | "success" | "warning" | "danger" | "info" | "outline";
  statusTone?: "ready" | "active" | "warning" | "danger" | "neutral";
  className?: string;
}

export function Metric({
  label,
  value,
  note,
  badge,
  badgeVariant = "neutral",
  className = "",
}: MetricProps) {
  return (
    <div className={`edos-metric-card ${className}`.trim()}>
      <div className="edos-metric-card__header">
        <span className="edos-metric-card__label">{label}</span>
        {badge && (
          typeof badge === "string" ? (
            <Badge variant={badgeVariant}>{badge}</Badge>
          ) : (
            badge
          )
        )}
      </div>
      <div className="edos-metric-card__value">
        {value}
      </div>
      {note && (
        <div className="edos-metric-card__note">
          {note}
        </div>
      )}
    </div>
  );
}
