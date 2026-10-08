import React from "react";
import { DecisionContext, ContextStatus } from "../../lib/types/context";
import { Badge, BadgeVariant } from "../ui/badge";
import { StatusIndicator, StatusState } from "../ui/status-indicator";

export interface ContextHeaderProps {
  context: DecisionContext;
}

function resolveStatusVariant(status: ContextStatus): {
  badgeVariant: BadgeVariant;
  statusTone: StatusState;
  label: string;
} {
  switch (status) {
    case "ELEVATED":
      return {
        badgeVariant: "danger",
        statusTone: "error",
        label: "ELEVATED CONTEXT",
      };
    case "ATTENTION":
      return {
        badgeVariant: "warning",
        statusTone: "warning",
        label: "ATTENTION REQUIRED",
      };
    case "NORMAL":
    default:
      return {
        badgeVariant: "success",
        statusTone: "ready",
        label: "NORMAL OPERATING STATE",
      };
  }
}

export function ContextHeader({ context }: ContextHeaderProps) {
  const { product, warehouse, status } = context;
  const statusMeta = resolveStatusVariant(status);

  return (
    <header className="edos-situation-header" aria-labelledby="situation-heading">
      <div className="edos-situation-header__top">
        <div className="edos-situation-header__breadcrumbs">
          <span className="edos-situation-header__tag">OPERATIONAL SITUATION</span>
          <span className="edos-situation-header__sep">/</span>
          <span className="edos-situation-header__sku-mono">{product.sku}</span>
          <span className="edos-situation-header__sep">@</span>
          <span className="edos-situation-header__wh-mono">{warehouse.code}</span>
        </div>

        <div className="edos-situation-header__status-badge">
          <StatusIndicator
            tone={statusMeta.statusTone}
            label={status}
            pulse={status !== "NORMAL"}
          />
          <Badge variant={statusMeta.badgeVariant}>{statusMeta.label}</Badge>
        </div>
      </div>

      <div className="edos-situation-header__main">
        <div className="edos-situation-header__title-group">
          <div className="edos-situation-header__meta-row">
            <span className="edos-situation-header__sku-pill">{product.sku}</span>
            <Badge variant="outline">{product.category}</Badge>
            <span className="edos-situation-header__bullet">•</span>
            <span className="edos-situation-header__location">
              {warehouse.name} ({warehouse.code}) — {warehouse.location}
            </span>
          </div>
          <h1 id="situation-heading" className="edos-situation-header__title">
            {product.name}
          </h1>
          <p className="edos-situation-header__subtitle">
            Synthesized operational snapshot across inventory, observed demand, and supplier intelligence.
          </p>
        </div>

        <div className="edos-situation-header__boundary-tag">
          <span className="edos-situation-header__boundary-title">
            CONTEXT BOUNDARY (DAY 10)
          </span>
          <span className="edos-situation-header__boundary-desc">
            What do we know about this situation?
          </span>
        </div>
      </div>
    </header>
  );
}
