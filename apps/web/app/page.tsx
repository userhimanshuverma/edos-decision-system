import React from "react";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { StatusIndicator } from "../components/ui/status-indicator";

export default function OverviewPage() {
  return (
    <div className="edos-overview">
      {/* Overview Hero Header */}
      <section className="edos-overview__hero" aria-labelledby="overview-title">
        <div className="edos-overview__hero-pre">
          <Badge variant="default">Foundation Phase</Badge>
          <Badge variant="neutral">Day 2</Badge>
        </div>
        <h1 id="overview-title" className="edos-overview__hero-title">
          Overview
        </h1>
        <h2 className="edos-overview__hero-subtitle">
          Operational Decision System
        </h2>
        <p className="edos-overview__hero-description">
          Monitor and review operational decisions from one workspace.
        </p>
      </section>

      {/* Primary Operational Metric & Status Cards */}
      <section
        className="edos-metrics-grid"
        aria-label="Operational high-level metrics"
      >
        {/* Card 1: Active Decisions */}
        <div className="edos-metric-card">
          <div className="edos-metric-card__header">
            <span className="edos-metric-card__label">Active Decisions</span>
            <Badge variant="neutral">Idle</Badge>
          </div>
          <div className="edos-metric-card__value">—</div>
          <span className="edos-metric-card__note">
            No decision runs currently in progress
          </span>
        </div>

        {/* Card 2: Pending Reviews */}
        <div className="edos-metric-card">
          <div className="edos-metric-card__header">
            <span className="edos-metric-card__label">Pending Reviews</span>
            <Badge variant="neutral">Queue 0</Badge>
          </div>
          <div className="edos-metric-card__value">—</div>
          <span className="edos-metric-card__note">
            Human approval queue awaiting triggers
          </span>
        </div>

        {/* Card 3: System Status */}
        <div className="edos-metric-card">
          <div className="edos-metric-card__header">
            <span className="edos-metric-card__label">System Status</span>
            <Badge variant="success">READY</Badge>
          </div>
          <div className="edos-metric-card__value" style={{ color: "var(--color-success)" }}>
            READY
          </div>
          <div className="edos-metric-card__note">
            <StatusIndicator tone="ready" label="FastAPI & Web Shell Operational" pulse />
          </div>
        </div>
      </section>

      {/* Recent Operational Activity Section */}
      <section className="edos-section" aria-labelledby="activity-section-title">
        <div className="edos-section__header">
          <h3 id="activity-section-title" className="edos-section__title">
            Recent Activity
          </h3>
          <span className="edos-section__tag">LOG PROTOCOL: V1</span>
        </div>

        <Card>
          <div className="edos-empty-state">
            <div className="edos-empty-state__icon-wrapper" aria-hidden="true">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <h4 className="edos-empty-state__title">
              No operational decisions yet
            </h4>
            <p className="edos-empty-state__description">
              Decision activity will appear here once EDOS begins processing
              operational scenarios.
            </p>
            <div className="edos-empty-state__meta">
              <span className="edos-status__dot" style={{ background: "var(--color-accent)", width: 6, height: 6 }} />
              <span>Awaiting scenario execution triggers</span>
            </div>
          </div>
        </Card>
      </section>

      {/* Operational Decision Pipeline Architecture Reference */}
      <section className="edos-section" aria-labelledby="pipeline-section-title">
        <div className="edos-section__header">
          <h3 id="pipeline-section-title" className="edos-section__title">
            Operational Decision Pipeline
          </h3>
          <span className="edos-section__tag">EDOS SPECIFICATION</span>
        </div>

        <Card
          description="Standard decision workflow sequence for operational events."
        >
          <div className="edos-pipeline-flow" role="list" aria-label="Decision workflow steps">
            {[
              "Situation",
              "Context",
              "Actions",
              "Validation",
              "Scenarios",
              "Result",
              "Evidence",
              "AI Explanation",
              "Human Approval",
            ].map((step, idx, arr) => (
              <React.Fragment key={step}>
                <div className="edos-pipeline-step" role="listitem">
                  <span className="edos-pipeline-step__num">0{idx + 1}</span>
                  <span>{step}</span>
                </div>
                {idx < arr.length - 1 && (
                  <span className="edos-pipeline-arrow" aria-hidden="true">
                    →
                  </span>
                )}
              </React.Fragment>
            ))}
          </div>
        </Card>
      </section>
    </div>
  );
}
