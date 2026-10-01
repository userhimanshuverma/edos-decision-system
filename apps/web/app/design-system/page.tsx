"use client";

import React, { useState } from "react";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { StatusIndicator } from "../../components/ui/status-indicator";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { Tabs } from "../../components/ui/tabs";
import { Tooltip } from "../../components/ui/tooltip";
import { Metric } from "../../components/ui/metric";
import { DataTable, ColumnDef } from "../../components/ui/data-table";
import { KeyValue } from "../../components/ui/key-value";
import { Timeline } from "../../components/ui/timeline";
import { EmptyState } from "../../components/ui/empty-state";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorState } from "../../components/ui/error-state";
import { DecisionBadge, DecisionState } from "../../components/ui/decision-badge";

interface DemoTableRow extends Record<string, unknown> {
  id: string;
  code: string;
  item: string;
  category: string;
  leadTimeDays: number;
  status: string;
}

export default function DesignSystemPage() {
  const [activeTab, setActiveTab] = useState("all");
  const [inputValue, setInputValue] = useState("");
  const [selectValue, setSelectValue] = useState("option-1");
  const [tableDensity, setTableDensity] = useState<"comfortable" | "compact">("comfortable");
  const [selectedRowId, setSelectedRowId] = useState<string>("row-1");

  const demoTableColumns: ColumnDef<DemoTableRow>[] = [
    {
      key: "code",
      header: "Code",
      render: (row) => (
        <span className="edos-type-mono" style={{ fontWeight: 600 }}>
          {row.code}
        </span>
      ),
    },
    { key: "item", header: "Demonstration Item" },
    { key: "category", header: "Category" },
    {
      key: "leadTimeDays",
      header: "Lead Time (Days)",
      align: "right",
      render: (row) => (
        <span className="edos-type-mono">{row.leadTimeDays}d</span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (row) => {
        if (row.status === "ACTIVE") return <Badge variant="success">Active</Badge>;
        if (row.status === "PENDING") return <Badge variant="warning">Pending</Badge>;
        return <Badge variant="neutral">Standby</Badge>;
      },
    },
  ];

  const demoTableData: DemoTableRow[] = [
    {
      id: "row-1",
      code: "DEMO-001",
      item: "Standard Component A",
      category: "Mechanical",
      leadTimeDays: 7,
      status: "ACTIVE",
    },
    {
      id: "row-2",
      code: "DEMO-002",
      item: "Modular Controller B",
      category: "Electronics",
      leadTimeDays: 14,
      status: "PENDING",
    },
    {
      id: "row-3",
      code: "DEMO-003",
      item: "Auxiliary Cable C",
      category: "Wiring",
      leadTimeDays: 3,
      status: "STANDBY",
    },
  ];

  return (
    <div className="edos-showcase">
      {/* Header */}
      <header className="edos-showcase__header">
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <Badge variant="default">Design System</Badge>
          <Badge variant="neutral">Light Enterprise Theme</Badge>
        </div>
        <h1 className="edos-type-display">EDOS Design System Specification</h1>
        <p className="edos-type-body">
          Living reference catalog and token specification for the Enterprise Decision Operating System.
        </p>
      </header>

      {/* 1. Typography */}
      <section className="edos-showcase__section" aria-labelledby="section-typography">
        <div className="edos-showcase__section-head">
          <h2 id="section-typography" className="edos-type-section-title">1. Typography Hierarchy</h2>
          <p className="edos-type-metadata">Inter (Sans-serif) and JetBrains Mono (Technical Monospace) token hierarchy.</p>
        </div>

        <Card>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <span className="edos-type-label">Display</span>
              <p className="edos-type-display">30px / 1.875rem — Operational Command Overview</p>
            </div>
            <div>
              <span className="edos-type-label">Page Title</span>
              <h1 className="edos-type-page-title">24px / 1.5rem — Decision Pipeline Verification</h1>
            </div>
            <div>
              <span className="edos-type-label">Section Title</span>
              <h2 className="edos-type-section-title">18px / 1.125rem — Candidate Action Screening</h2>
            </div>
            <div>
              <span className="edos-type-label">Card Title</span>
              <h3 className="edos-type-card-title">15px / 0.9375rem — Constraint Evaluation Matrix</h3>
            </div>
            <div>
              <span className="edos-type-label">Body</span>
              <p className="edos-type-body">
                14px / 0.875rem — Deterministic calculations evaluate candidate actions against hard constraints, policies, and budgets.
              </p>
            </div>
            <div>
              <span className="edos-type-label">Body Small</span>
              <p className="edos-type-body-sm">
                13px / 0.8125rem — Detailed parameter footnotes, supporting calculations, and input provenance.
              </p>
            </div>
            <div>
              <span className="edos-type-label">Metadata</span>
              <p className="edos-type-metadata">
                12px / 0.75rem — Last evaluated timestamp: 2026-10-02T00:00:00Z • Engine version: EDOS-OP-0.1
              </p>
            </div>
            <div>
              <span className="edos-type-label">Label / Monospace Tag</span>
              <p className="edos-type-label">11px / 0.6875rem — POLICY PROTOCOL: ISO-9001-A</p>
            </div>
            <div>
              <span className="edos-type-label">Technical Monospace</span>
              <p className="edos-type-mono">HASH: 8f9b3a1d4e2c7a0f • RESULT: PASS_DETERMINISTIC</p>
            </div>
          </div>
        </Card>
      </section>

      {/* 2. Colors & Semantic Tokens */}
      <section className="edos-showcase__section" aria-labelledby="section-colors">
        <div className="edos-showcase__section-head">
          <h2 id="section-colors" className="edos-type-section-title">2. Color & Semantic Tokens</h2>
          <p className="edos-type-metadata">Restrained neutral base with purposeful high-contrast semantic accents.</p>
        </div>

        <div className="edos-showcase__grid edos-showcase__grid--4">
          <div className="edos-swatch">
            <div className="edos-swatch__color" style={{ background: "var(--background)", borderBottom: "1px solid var(--border)" }} />
            <div className="edos-swatch__meta">
              <span className="edos-swatch__name">Background</span>
              <span className="edos-swatch__token">--background (#f8fafc)</span>
            </div>
          </div>

          <div className="edos-swatch">
            <div className="edos-swatch__color" style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }} />
            <div className="edos-swatch__meta">
              <span className="edos-swatch__name">Surface</span>
              <span className="edos-swatch__token">--surface (#ffffff)</span>
            </div>
          </div>

          <div className="edos-swatch">
            <div className="edos-swatch__color" style={{ background: "var(--surface-subtle)" }} />
            <div className="edos-swatch__meta">
              <span className="edos-swatch__name">Surface Subtle</span>
              <span className="edos-swatch__token">--surface-subtle (#f1f5f9)</span>
            </div>
          </div>

          <div className="edos-swatch">
            <div className="edos-swatch__color" style={{ background: "var(--border-strong)" }} />
            <div className="edos-swatch__meta">
              <span className="edos-swatch__name">Border Strong</span>
              <span className="edos-swatch__token">--border-strong (#cbd5e1)</span>
            </div>
          </div>

          <div className="edos-swatch">
            <div className="edos-swatch__color" style={{ background: "var(--accent)" }} />
            <div className="edos-swatch__meta">
              <span className="edos-swatch__name">Accent (Primary)</span>
              <span className="edos-swatch__token">--accent (#0284c7)</span>
            </div>
          </div>

          <div className="edos-swatch">
            <div className="edos-swatch__color" style={{ background: "var(--success)" }} />
            <div className="edos-swatch__meta">
              <span className="edos-swatch__name">Success</span>
              <span className="edos-swatch__token">--success (#16a34a)</span>
            </div>
          </div>

          <div className="edos-swatch">
            <div className="edos-swatch__color" style={{ background: "var(--warning)" }} />
            <div className="edos-swatch__meta">
              <span className="edos-swatch__name">Warning</span>
              <span className="edos-swatch__token">--warning (#d97706)</span>
            </div>
          </div>

          <div className="edos-swatch">
            <div className="edos-swatch__color" style={{ background: "var(--danger)" }} />
            <div className="edos-swatch__meta">
              <span className="edos-swatch__name">Danger</span>
              <span className="edos-swatch__token">--danger (#dc2626)</span>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Buttons */}
      <section className="edos-showcase__section" aria-labelledby="section-buttons">
        <div className="edos-showcase__section-head">
          <h2 id="section-buttons" className="edos-type-section-title">3. Button System</h2>
          <p className="edos-type-metadata">Variants: primary, secondary, outline, ghost, danger. Sizes: sm, md, lg.</p>
        </div>

        <Card>
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            <div>
              <span className="edos-type-label">Variants (Medium)</span>
              <div style={{ display: "flex", gap: "12px", marginTop: "8px", flexWrap: "wrap" }}>
                <Button variant="primary">Primary Action</Button>
                <Button variant="secondary">Secondary Action</Button>
                <Button variant="outline">Outline Button</Button>
                <Button variant="ghost">Ghost Button</Button>
                <Button variant="danger">Danger Action</Button>
              </div>
            </div>

            <div>
              <span className="edos-type-label">Sizes</span>
              <div style={{ display: "flex", gap: "12px", alignItems: "center", marginTop: "8px", flexWrap: "wrap" }}>
                <Button variant="primary" size="sm">Small (28px)</Button>
                <Button variant="primary" size="md">Medium (34px)</Button>
                <Button variant="primary" size="lg">Large (40px)</Button>
              </div>
            </div>

            <div>
              <span className="edos-type-label">States</span>
              <div style={{ display: "flex", gap: "12px", marginTop: "8px", flexWrap: "wrap" }}>
                <Button variant="primary" disabled>Primary Disabled</Button>
                <Button variant="secondary" disabled>Secondary Disabled</Button>
                <Button variant="outline" disabled>Outline Disabled</Button>
              </div>
            </div>
          </div>
        </Card>
      </section>

      {/* 4. Cards */}
      <section className="edos-showcase__section" aria-labelledby="section-cards">
        <div className="edos-showcase__section-head">
          <h2 id="section-cards" className="edos-type-section-title">4. Card System</h2>
          <p className="edos-type-metadata">Standard card and elevated card with headers, descriptions, actions, and footers.</p>
        </div>

        <div className="edos-showcase__grid edos-showcase__grid--2">
          <Card
            title="Standard Enterprise Card"
            description="Crisp 1px border with surface background and controlled radius."
            headerAction={<Button variant="outline" size="sm">Action</Button>}
            footer="Card footer note: verified deterministic payload"
          >
            <p className="edos-type-body">
              Standard containers maintain predictable padding and crisp borders for technical data display.
            </p>
          </Card>

          <Card
            title="Elevated Enterprise Card"
            description="Subtle soft elevation for floating or highlighted focus cards."
            elevated
            headerAction={<Badge variant="default">Highlighted</Badge>}
            footer="Elevated footer note: active operational focus"
          >
            <p className="edos-type-body">
              Elevated surfaces provide subtle depth separation without excessive dark drop shadows.
            </p>
          </Card>
        </div>
      </section>

      {/* 5. Badges */}
      <section className="edos-showcase__section" aria-labelledby="section-badges">
        <div className="edos-showcase__section-head">
          <h2 id="section-badges" className="edos-type-section-title">5. Badge System</h2>
          <p className="edos-type-metadata">Semantic badges designed for high legibility on light backgrounds.</p>
        </div>

        <Card>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
            <Badge variant="default">Default</Badge>
            <Badge variant="neutral">Neutral</Badge>
            <Badge variant="success">Success</Badge>
            <Badge variant="warning">Warning</Badge>
            <Badge variant="danger">Danger</Badge>
            <Badge variant="info">Info</Badge>
            <Badge variant="outline">Outline</Badge>
          </div>
        </Card>
      </section>

      {/* 6. Status Indicators */}
      <section className="edos-showcase__section" aria-labelledby="section-status">
        <div className="edos-showcase__section-head">
          <h2 id="section-status" className="edos-type-section-title">6. Status Indicators</h2>
          <p className="edos-type-metadata">Semantic state indicators with accessible labels and restrained pulse.</p>
        </div>

        <Card>
          <div style={{ display: "flex", gap: "24px", flexWrap: "wrap", alignItems: "center" }}>
            <StatusIndicator tone="ready" label="System Ready" pulse />
            <StatusIndicator tone="active" label="Pipeline Active" pulse />
            <StatusIndicator tone="processing" label="Simulating Scenarios" />
            <StatusIndicator tone="pending" label="Pending Approval" />
            <StatusIndicator tone="warning" label="SLA Warning" />
            <StatusIndicator tone="error" label="Constraint Violation" />
            <StatusIndicator tone="neutral" label="Standby" />
          </div>
        </Card>
      </section>

      {/* 7. Decision State Visual Language */}
      <section className="edos-showcase__section" aria-labelledby="section-decision-states">
        <div className="edos-showcase__section-head">
          <h2 id="section-decision-states" className="edos-type-section-title">7. Decision State Visual Language</h2>
          <p className="edos-type-metadata">
            Design tokens codifying future EDOS decision lifecycle states (design representations only).
          </p>
        </div>

        <Card>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
            {(
              [
                "Detected",
                "Processing",
                "Validated",
                "Recommended",
                "Pending Review",
                "Approved",
                "Rejected",
                "Escalated",
              ] as DecisionState[]
            ).map((state) => (
              <DecisionBadge key={state} state={state} />
            ))}
          </div>
        </Card>
      </section>

      {/* 8. Form Primitives: Input & Select */}
      <section className="edos-showcase__section" aria-labelledby="section-forms">
        <div className="edos-showcase__section-head">
          <h2 id="section-forms" className="edos-type-section-title">8. Form Primitives</h2>
          <p className="edos-type-metadata">Accessible inputs and selects with validation and helper text.</p>
        </div>

        <Card>
          <div className="edos-showcase__grid edos-showcase__grid--3">
            <Input
              label="Standard Input"
              placeholder="Enter search filter..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              helperText="Filter criteria for scenario parameters"
            />

            <Input
              label="Input with Error"
              defaultValue="INVALID_RANGE_999"
              error="Value exceeds maximum allowable threshold"
            />

            <Input
              label="Disabled Input"
              defaultValue="FIXED_PROTOCOL_V1"
              disabled
              helperText="Locked by governance policy"
            />

            <Select
              label="Standard Select"
              value={selectValue}
              onChange={(e) => setSelectValue(e.target.value)}
              options={[
                { value: "option-1", label: "Option 1: Expedited Freight" },
                { value: "option-2", label: "Option 2: Alternative Supplier" },
                { value: "option-3", label: "Option 3: Split Order" },
              ]}
              helperText="Candidate action selection"
            />

            <Select
              label="Select with Error"
              defaultValue=""
              error="A decision rationale category is required"
              options={[
                { value: "", label: "-- Choose Category --" },
                { value: "cost", label: "Cost Optimization" },
              ]}
            />

            <Select
              label="Disabled Select"
              defaultValue="locked"
              disabled
              options={[{ value: "locked", label: "Locked Configuration" }]}
              helperText="Cannot be changed during execution"
            />
          </div>
        </Card>
      </section>

      {/* 9. Tabs */}
      <section className="edos-showcase__section" aria-labelledby="section-tabs">
        <div className="edos-showcase__section-head">
          <h2 id="section-tabs" className="edos-type-section-title">9. Tabs Component</h2>
          <p className="edos-type-metadata">Clean border-bottom enterprise tabs with keyboard accessibility.</p>
        </div>

        <Card>
          <Tabs
            activeTab={activeTab}
            onChange={setActiveTab}
            tabs={[
              { id: "all", label: "All Decisions", badge: 3 },
              { id: "pending", label: "Pending Sign-off", badge: 1 },
              { id: "approved", label: "Approved Records", badge: 2 },
              { id: "archived", label: "Archived", disabled: true },
            ]}
          />
          <div style={{ padding: "16px 0 0" }}>
            <span className="edos-type-metadata">Active View: </span>
            <span className="edos-type-mono" style={{ fontWeight: 600 }}>{activeTab}</span>
          </div>
        </Card>
      </section>

      {/* 10. Tooltip */}
      <section className="edos-showcase__section" aria-labelledby="section-tooltip">
        <div className="edos-showcase__section-head">
          <h2 id="section-tooltip" className="edos-type-section-title">10. Tooltip Pattern</h2>
          <p className="edos-type-metadata">Lightweight contextual explanations for icons or compact controls.</p>
        </div>

        <Card>
          <div style={{ display: "flex", gap: "24px", alignItems: "center" }}>
            <Tooltip content="Tooltip positioned on top" position="top">
              <Button variant="secondary" size="sm">Hover Me (Top)</Button>
            </Tooltip>

            <Tooltip content="Tooltip positioned on bottom" position="bottom">
              <Button variant="secondary" size="sm">Hover Me (Bottom)</Button>
            </Tooltip>

            <Tooltip content="Deterministic seed: 0x4f12" position="right">
              <span className="edos-badge edos-badge--neutral" tabIndex={0} style={{ cursor: "help" }}>
                Provenance Info (?)
              </span>
            </Tooltip>
          </div>
        </Card>
      </section>

      {/* 11. Metrics / KPIs */}
      <section className="edos-showcase__section" aria-labelledby="section-metrics">
        <div className="edos-showcase__section-head">
          <h2 id="section-metrics" className="edos-type-section-title">11. Metric / KPI Components</h2>
          <p className="edos-type-metadata">Standard operational KPI card foundation (demonstration values only).</p>
        </div>

        <div className="edos-metrics-grid">
          <Metric
            label="Active Decisions"
            value="—"
            badge="Idle"
            badgeVariant="neutral"
            note="Demonstration placeholder: awaiting execution"
          />

          <Metric
            label="Pending Reviews"
            value="—"
            badge="Queue 0"
            badgeVariant="neutral"
            note="Demonstration placeholder: human sign-off"
          />

          <Metric
            label="System Status"
            value={<span style={{ color: "var(--success)" }}>READY</span>}
            badge="READY"
            badgeVariant="success"
            note={
              <StatusIndicator tone="ready" label="All Subsystems Online" pulse />
            }
          />
        </div>
      </section>

      {/* 12. Data Table */}
      <section className="edos-showcase__section" aria-labelledby="section-table">
        <div className="edos-showcase__section-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 id="section-table" className="edos-type-section-title">12. Data Table Foundation</h2>
            <p className="edos-type-metadata">Enterprise table with compact/comfortable density, selection, and numeric alignment.</p>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <Button
              variant={tableDensity === "comfortable" ? "primary" : "secondary"}
              size="sm"
              onClick={() => setTableDensity("comfortable")}
            >
              Comfortable
            </Button>
            <Button
              variant={tableDensity === "compact" ? "primary" : "secondary"}
              size="sm"
              onClick={() => setTableDensity("compact")}
            >
              Compact
            </Button>
          </div>
        </div>

        <DataTable
          columns={demoTableColumns}
          data={demoTableData}
          density={tableDensity}
          selectedId={selectedRowId}
          onRowClick={(row) => setSelectedRowId(row.id as string)}
          caption="Demonstration DataTable showcase"
        />
        <span className="edos-type-metadata" style={{ marginTop: "4px" }}>
          * Click a row to toggle selection state (currently selected: {selectedRowId})
        </span>
      </section>

      {/* 13. Key-Value Display */}
      <section className="edos-showcase__section" aria-labelledby="section-kv">
        <div className="edos-showcase__section-head">
          <h2 id="section-kv" className="edos-type-section-title">13. Key-Value Operational Display</h2>
          <p className="edos-type-metadata">Structured operational attribute display for entity details.</p>
        </div>

        <Card title="Operational Entity Specification" description="Demonstration key-value metadata layout.">
          <KeyValue
            columns={4}
            items={[
              { label: "Product SKU", value: "SKU-DEMO-001", monospace: true },
              { label: "Supplier Entity", value: "Apex Components Ltd" },
              { label: "Lead Time", value: "7 Days", monospace: true },
              {
                label: "Operational State",
                value: "Validated",
                badge: <Badge variant="success">Pass</Badge>,
              },
            ]}
          />
        </Card>
      </section>

      {/* 14. Timeline */}
      <section className="edos-showcase__section" aria-labelledby="section-timeline">
        <div className="edos-showcase__section-head">
          <h2 id="section-timeline" className="edos-type-section-title">14. Vertical Timeline Component</h2>
          <p className="edos-type-metadata">Step sequence visualizing progression through operational workflow stages.</p>
        </div>

        <Card>
          <Timeline
            items={[
              {
                id: "step-1",
                title: "01 Situation Detected",
                description: "Operational trigger ingested and normalized into system schema.",
                time: "00:01:12",
                status: "completed",
              },
              {
                id: "step-2",
                title: "02 Context Assembled",
                description: "Relevant operational parameters and historical data aggregated.",
                time: "00:01:15",
                status: "completed",
              },
              {
                id: "step-3",
                title: "03 Actions Generated & Validated",
                description: "Candidate actions screened against hard constraints and business policies.",
                time: "00:01:18",
                status: "current",
                badge: <Badge variant="default">In Progress</Badge>,
              },
              {
                id: "step-4",
                title: "04 Scenarios & Scoring",
                description: "Deterministic simulations computing trade-off projections.",
                status: "upcoming",
              },
            ]}
          />
        </Card>
      </section>

      {/* 15. States: Empty, Loading, Error */}
      <section className="edos-showcase__section" aria-labelledby="section-states">
        <div className="edos-showcase__section-head">
          <h2 id="section-states" className="edos-type-section-title">15. Intentional Operational States</h2>
          <p className="edos-type-metadata">Enterprise empty, loading (spinner & skeleton), and error states.</p>
        </div>

        <div className="edos-showcase__grid edos-showcase__grid--3">
          <Card title="Empty State">
            <EmptyState
              title="No operational decisions yet"
              description="Decision activity will appear here once EDOS begins processing operational scenarios."
              meta={
                <span className="edos-status edos-status--active">
                  <span className="edos-status__dot" />
                  <span>Awaiting triggers</span>
                </span>
              }
            />
          </Card>

          <Card title="Loading State (Spinner)">
            <LoadingState
              label="Simulating Scenarios..."
              sublabel="Evaluating 12 candidate combinations"
            />
          </Card>

          <Card title="Loading State (Skeleton)">
            <LoadingState type="skeleton" label="Loading data table..." />
          </Card>
        </div>

        <div style={{ marginTop: "16px" }}>
          <ErrorState
            title="Policy Constraint Violation Detected"
            message="Selected intervention violates maximum budget ceiling authorized under protocol SLA-4."
            code="ERR_POLICY_BUDGET_CEILING_EXCEEDED"
            onRetry={() => alert("Simulated retry clicked")}
            retryLabel="Re-evaluate Candidate Actions"
          />
        </div>
      </section>
    </div>
  );
}
