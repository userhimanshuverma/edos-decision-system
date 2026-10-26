import React from "react";
import Link from "next/link";
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
          <Badge variant="neutral">Day 28</Badge>
          <Badge variant="success">Workspace Live</Badge>
        </div>
        <h1 id="overview-title" className="edos-overview__hero-title">
          Overview
        </h1>
        <h2 className="edos-overview__hero-subtitle">
          Operational Decision System
        </h2>
        <p className="edos-overview__hero-description">
          Monitor and review operational decisions from one cohesive workspace.
        </p>
      </section>

      {/* Primary Operational Metric & Status Cards */}
      <section
        className="edos-metrics-grid"
        aria-label="Operational high-level metrics"
      >
        {/* Card 1: Active Decisions */}
        <Metric
          label="Decision Workspace"
          value={<Link href="/decisions" style={{ color: "var(--accent)", textDecoration: "none" }}>Open →</Link>}
          badge="Live"
          badgeVariant="success"
          note="Review decisions, actions, trust & AI explanation"
        />

        {/* Card 2: Pending Reviews */}
        <Metric
          label="Human Approval Boundary"
          value={<span style={{ color: "var(--success)" }}>READY</span>}
          badge="Evaluated"
          badgeVariant="success"
          note="System calculates. AI explains. Humans approve."
        />

        {/* Card 3: System Status */}
        <Metric
          label="System Status"
          value={<span style={{ color: "var(--success)" }}>OPERATIONAL</span>}
          badge="READY"
          badgeVariant="success"
          note={
            <StatusIndicator
              tone="ready"
              label="Decision Pipeline & Services Online"
              pulse
            />
          }
        />
      </section>

      {/* Decision Workspace Featured Section (Day 28) */}
      <section className="edos-section" aria-labelledby="workspace-section-title">
        <div className="edos-section__header">
          <h3 id="workspace-section-title" className="edos-section__title">
            Unified Decision Workspace
          </h3>
          <span className="edos-section__tag">DAY 28 MILESTONE — LIVE</span>
        </div>

        <Card
          title="Integrated Decision Review Experience"
          description="A single cohesive workspace connecting decision lifecycle, candidate actions, recommendation ranking, hard constraints, evidence sheets, provenance traces, decision replay, and local LLM explanation & Q&A."
          headerAction={
            <Link
              href="/decisions"
              className="edos-btn edos-btn--primary edos-btn--sm"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 18px",
                background: "var(--accent)",
                color: "#ffffff",
                borderRadius: "var(--radius-md)",
                fontWeight: 600,
                fontSize: "0.875rem",
                textDecoration: "none",
              }}
            >
              Open Decision Workspace →
            </Link>
          }
        >
          <div className="edos-overview-context-banner">
            <div className="edos-overview-context-banner__meta">
              <span className="edos-overview-context-sku">4 Integrated Sections</span>
              <span className="edos-overview-context-title">
                Overview &bull; Recommended Action &amp; Scenarios &bull; Evidence &amp; Decision Trust &bull; AI Explanation &amp; Q&amp;A
              </span>
            </div>
            <div className="edos-overview-context-banner__badges">
              <Badge variant="success">Deterministic Engine</Badge>
              <Badge variant="neutral">Lexicographic Dominance</Badge>
              <Badge variant="outline">Grounded AI</Badge>
            </div>
          </div>
        </Card>
      </section>

      {/* Operational Situation Context Workspace (Day 10) */}
      <section className="edos-section" aria-labelledby="context-section-title">
        <div className="edos-section__header">
          <h3 id="context-section-title" className="edos-section__title">
            Operational Situation Context
          </h3>
          <span className="edos-section__tag">DAY 10 MILESTONE — LIVE</span>
        </div>

        <Card
          title="Product & Warehouse Decision Context Workspace"
          description="Synthesized operational intelligence across inventory positions, observed demand trends, and upstream supplier parameters."
          headerAction={
            <Link
              href="/context"
              className="edos-btn edos-btn--primary edos-btn--sm"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 14px",
                background: "var(--accent)",
                color: "#ffffff",
                borderRadius: "var(--radius-md)",
                fontWeight: 600,
                fontSize: "0.8125rem",
              }}
            >
              Inspect Decision Context →
            </Link>
          }
        >
          <div className="edos-overview-context-banner">
            <div className="edos-overview-context-banner__meta">
              <span className="edos-overview-context-sku">SKU-ELEC-1001</span>
              <span className="edos-overview-context-title">
                Industrial IoT Gateway Edge-X @ Eastern Logistics Hub (WH-EAST-01)
              </span>
            </div>
            <div className="edos-overview-context-banner__badges">
              <Badge variant="warning">Status: ATTENTION</Badge>
              <Badge variant="neutral">Coverage: 29.4 days</Badge>
              <Badge variant="outline">Lead Time: 10 days</Badge>
            </div>
          </div>
        </Card>
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
