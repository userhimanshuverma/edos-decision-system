"use client";

import React, { useState } from "react";
import { ExplanationPanel } from "../explanation/explanation-panel";
import { DecisionQAPanel } from "../explanation/decision-qa-panel";
import { Tabs, TabItem } from "../ui/tabs";

export interface DecisionAISectionProps {
  decisionId: string;
  versionId?: string | null;
}

export function DecisionAISection({
  decisionId,
  versionId,
}: DecisionAISectionProps) {
  const [activeTab, setActiveTab] = useState<string>("explanation");

  const tabs: TabItem[] = [
    {
      id: "explanation",
      label: "AI Decision Explanation (Day 26)",
      badge: "Grounded LLM",
    },
    {
      id: "qa",
      label: "Interactive Decision Q&A (Day 27)",
      badge: "Audited Q&A",
    },
  ];

  return (
    <section className="edos-ws-section" aria-labelledby="ai-heading">
      <div className="edos-ws-section__header">
        <h2 id="ai-heading" className="edos-ws-section__title">
          Section D: AI Explanation and Decision Q&A
        </h2>
        <span className="edos-ws-section__tag">EXPLANATION LAYER</span>
      </div>

      <div className="edos-ws-ai-box">
        {/* Architectural Principle Banner */}
        <div className="edos-ws-ai-banner">
          <div className="edos-ws-ai-banner__icon" aria-hidden="true">
            🤖
          </div>
          <div className="edos-ws-ai-banner__content">
            <span className="edos-ws-ai-banner__principle">
              Core Architectural Principle: &quot;The system calculates. AI explains. Humans approve.&quot;
            </span>
            <p className="edos-ws-ai-banner__description">
              The AI explanation layer cannot recalculate parameters, mutate candidate actions, alter
              recommendation rankings, relax constraints, or approve decisions. It strictly explains
              the system&apos;s calculated outputs based on recorded facts, constraints, and explicit assumptions.
            </p>
          </div>
        </div>

        {/* AI Navigation Tabs */}
        <div style={{ marginBottom: "16px" }}>
          <Tabs
            tabs={tabs}
            activeTab={activeTab}
            onChange={(tabId) => setActiveTab(tabId)}
          />
        </div>

        {/* Tab 1: Decision Explanation */}
        {activeTab === "explanation" && (
          <div className="edos-ws-tab-pane">
            <ExplanationPanel
              key={`explanation-${decisionId}-${versionId || "latest"}`}
              initialDecisionId={decisionId}
              initialVersionId={versionId || undefined}
            />
          </div>
        )}

        {/* Tab 2: Decision Q&A */}
        {activeTab === "qa" && (
          <div className="edos-ws-tab-pane">
            <DecisionQAPanel
              key={`qa-${decisionId}-${versionId || "latest"}`}
              initialDecisionId={decisionId}
              initialVersionId={versionId || undefined}
            />
          </div>
        )}
      </div>
    </section>
  );
}
