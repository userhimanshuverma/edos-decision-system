import React from "react";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { StatusIndicator } from "../components/ui/status-indicator";
import { Metric } from "../components/ui/metric";
import { EmptyState } from "../components/ui/empty-state";

export default function OverviewPage() {
  return (
    <div className="edos-overview">
      {/* Overview Hero Header */}
      <section className="edos-overview__hero" aria-labelledby="overview-title">
        <div className="edos-overview__hero-pre">
          <Badge variant="default">Foundation Phase</Badge>
          <Badge variant="neutral">Day 3</Badge>
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
        <Metric
          label="Active Decisions"
          value="—"
          badge="Idle"
          badgeVariant="neutral"
          note="No decision runs currently in progress"
        />

        {/* Card 2: Pending Reviews */}
        <Metric
          label="Pending Reviews"
          value="—"
          badge="Queue 0"
          badgeVariant="neutral"
          note="Human approval queue awaiting triggers"
        />

        {/* Card 3: System Status */}
        <Metric
          label="System Status"
          value={<span style={{ color: "var(--success)" }}>READY</span>}
          badge="READY"
          badgeVariant="success"
          note={
            <StatusIndicator
              tone="ready"
              label="FastAPI & Web Shell Operational"
              pulse
            />
          }
        />
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
          <EmptyState
            title="No operational decisions yet"
            description="Decision activity will appear here once EDOS begins processing operational scenarios."
            meta={
              <span className="edos-status edos-status--active">
                <span className="edos-status__dot" />
                <span>Awaiting scenario execution triggers</span>
              </span>
            }
          />
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
