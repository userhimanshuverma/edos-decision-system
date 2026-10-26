"use client";

import React from "react";
import type { DecisionRecord, DecisionStatus } from "../../lib/types/decision";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

export interface WorkspaceHeaderProps {
  decisions: DecisionRecord[];
  activeDecision: DecisionRecord | null;
  onSelectDecision: (decisionId: string) => void;
  onCreateDecisionPrompt: () => void;
  isLoading?: boolean;
}

const LIFECYCLE_STAGES: DecisionStatus[] = [
  "DRAFT",
  "CONTEXTUALIZING",
  "CONSTRUCTING",
  "VALIDATING",
  "EVALUATING",
  "READY",
];

export function WorkspaceHeader({
  decisions,
  activeDecision,
  onSelectDecision,
  onCreateDecisionPrompt,
  isLoading = false,
}: WorkspaceHeaderProps) {
  const currentStatusIndex = activeDecision
    ? LIFECYCLE_STAGES.indexOf(activeDecision.status)
    : -1;

  return (
    <header className="edos-ws-header" aria-label="Decision workspace header">
      <div className="edos-ws-header__top">
        <div className="edos-ws-header__identity">
          <div className="edos-ws-header__meta-row">
            <Badge variant="default">Decision Workspace</Badge>
            <Badge variant="neutral">Day 28 Integration</Badge>
            {activeDecision && (
              <Badge
                variant={
                  activeDecision.status === "READY"
                    ? "success"
                    : activeDecision.status === "DRAFT"
                    ? "neutral"
                    : "warning"
                }
              >
                {activeDecision.status}
              </Badge>
            )}
          </div>

          <div className="edos-ws-header__title-row">
            <h1 className="edos-ws-header__title">
              {activeDecision ? activeDecision.id : "Operational Decision Workspace"}
            </h1>
            {activeDecision && (
              <span className="edos-ws-header__subtitle">
                {activeDecision.product_id} @ {activeDecision.warehouse_id}
              </span>
            )}
          </div>

          {activeDecision && (
            <div className="edos-ws-header__context-tags">
              <span className="edos-ws-tag">
                <strong>Created:</strong>{" "}
                {new Date(activeDecision.created_at).toLocaleString("en-US", {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </span>
              <span className="edos-ws-tag">
                <strong>Product ID:</strong> {activeDecision.product_id}
              </span>
              <span className="edos-ws-tag">
                <strong>Warehouse ID:</strong> {activeDecision.warehouse_id}
              </span>
            </div>
          )}
        </div>

        {/* Decision Switcher & Action Controls */}
        <div className="edos-ws-header__controls">
          <div className="edos-ws-switcher">
            <label htmlFor="decision-selector" className="edos-ws-switcher__label">
              Active Decision:
            </label>
            <select
              id="decision-selector"
              className="edos-select"
              value={activeDecision?.id || ""}
              onChange={(e) => onSelectDecision(e.target.value)}
              disabled={isLoading || decisions.length === 0}
              aria-label="Select active business decision"
            >
              {decisions.length === 0 ? (
                <option value="">No decisions recorded</option>
              ) : (
                decisions.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.id} ({d.product_id} @ {d.warehouse_id} - {d.status})
                  </option>
                ))
              )}
            </select>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={onCreateDecisionPrompt}
            disabled={isLoading}
          >
            + New Decision
          </Button>
        </div>
      </div>

      {/* Lifecycle Progress Pipeline */}
      {activeDecision && (
        <div className="edos-ws-lifecycle" aria-label="Lifecycle progression">
          <div className="edos-ws-lifecycle__label">
            <span>Deterministic Lifecycle State Machine:</span>
          </div>
          <div className="edos-ws-lifecycle__stepper" role="list">
            {LIFECYCLE_STAGES.map((stage, idx) => {
              const isPast = idx < currentStatusIndex;
              const isCurrent = idx === currentStatusIndex;
              const isFuture = idx > currentStatusIndex;

              let stepClass = "edos-ws-step";
              if (isCurrent) stepClass += " edos-ws-step--current";
              else if (isPast) stepClass += " edos-ws-step--completed";
              else if (isFuture) stepClass += " edos-ws-step--pending";

              return (
                <div key={stage} className={stepClass} role="listitem">
                  <span className="edos-ws-step__dot" aria-hidden="true">
                    {isPast ? "✓" : idx + 1}
                  </span>
                  <span className="edos-ws-step__name">{stage}</span>
                  {idx < LIFECYCLE_STAGES.length - 1 && (
                    <span className="edos-ws-step__connector" aria-hidden="true" />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Human Approval Boundary Banner */}
      {activeDecision && activeDecision.status === "READY" && (
        <div className="edos-ws-approval-boundary" role="region" aria-label="Human approval boundary">
          <div className="edos-ws-approval-boundary__icon" aria-hidden="true">
            ℹ️
          </div>
          <div className="edos-ws-approval-boundary__body">
            <strong>Human Approval Boundary:</strong> Decision is in terminal state{" "}
            <Badge variant="success">READY</Badge>. System calculation, constraint validation, and
            evidence compilation are complete and awaiting human reviewer evaluation.
            <div className="edos-ws-approval-boundary__note">
              <em>Architecture Invariant:</em> EDOS lifecycle terminates at <code>READY</code>. Approval
              transitions and external purchase order execution are not implemented in the current backend
              service; decisions are reviewed by human decision-makers without automated approval bypass.
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
