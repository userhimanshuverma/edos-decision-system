"use client";

import React, { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import type {
  DecisionRecord,
  CandidateActionRecord,
  RecommendationRecord,
  DecisionValidationRecord,
  DecisionEvidenceSheetRecord,
  DecisionProvenanceTraceRecord,
  DecisionReplayRecord,
  DecisionScenarioRecord,
  DecisionVersionRecord,
  DecisionStatus,
} from "../../lib/types/decision";
import type { DecisionContext } from "../../lib/types/context";
import {
  listDecisions,
  createDecision,
  updateDecisionStatus,
  getCandidateActions,
  createCandidateAction,
  getDecisionRecommendation,
  getDecisionValidation,
  getDecisionEvidenceSheet,
  getDecisionProvenance,
  getDecisionReplay,
  getDecisionScenarios,
  getDecisionVersions,
} from "../../lib/api/decision";
import { getDecisionContext, PRESET_SITUATIONS } from "../../lib/api/context";

import { WorkspaceHeader } from "../../components/workspace/workspace-header";
import { DecisionOverviewSection } from "../../components/workspace/decision-overview-section";
import { RecommendedActionsScenariosSection } from "../../components/workspace/recommended-actions-scenarios-section";
import { EvidenceTrustSection } from "../../components/workspace/evidence-trust-section";
import { DecisionAISection } from "../../components/workspace/decision-ai-section";

import { LoadingState } from "../../components/ui/loading-state";
import { EmptyState } from "../../components/ui/empty-state";
import { ErrorState } from "../../components/ui/error-state";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";

function DecisionWorkspaceContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const urlDecisionId = searchParams?.get("id");

  // Core Decision Collections & Active Decision
  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);
  const [activeDecisionId, setActiveDecisionId] = useState<string | null>(urlDecisionId || null);
  const [activeDecision, setActiveDecision] = useState<DecisionRecord | null>(null);

  // Loaded operational details for active decision
  const [context, setContext] = useState<DecisionContext | null>(null);
  const [candidateActions, setCandidateActions] = useState<CandidateActionRecord[]>([]);
  const [recommendation, setRecommendation] = useState<RecommendationRecord | null>(null);
  const [validation, setValidation] = useState<DecisionValidationRecord | null>(null);
  const [evidenceSheet, setEvidenceSheet] = useState<DecisionEvidenceSheetRecord | null>(null);
  const [provenance, setProvenance] = useState<DecisionProvenanceTraceRecord | null>(null);
  const [replay, setReplay] = useState<DecisionReplayRecord | null>(null);
  const [scenarios, setScenarios] = useState<DecisionScenarioRecord[]>([]);
  const [versions, setVersions] = useState<DecisionVersionRecord[]>([]);

  // State indicators
  const [isLoadingDecisions, setIsLoadingDecisions] = useState<boolean>(true);
  const [isLoadingDetails, setIsLoadingDetails] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // New decision creation modal/bar state
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newProductId, setNewProductId] = useState<string>("prod-001");
  const [newWarehouseId, setNewWarehouseId] = useState<string>("wh-001");
  const [isCreatingDecision, setIsCreatingDecision] = useState<boolean>(false);

  // View section focus filter (all or specific tab)
  const [activeSection, setActiveSection] = useState<string>("all");

  // Load decision list
  const loadDecisionsList = useCallback(async (selectId?: string) => {
    setIsLoadingDecisions(true);
    setErrorMessage(null);
    try {
      const records = await listDecisions();
      setDecisions(records);

      if (records.length > 0) {
        const targetId =
          selectId ||
          (urlDecisionId && records.some((d) => d.id === urlDecisionId)
            ? urlDecisionId
            : records[0].id);
        setActiveDecisionId(targetId);
        const match = records.find((d) => d.id === targetId) || records[0];
        setActiveDecision(match);
      } else {
        setActiveDecisionId(null);
        setActiveDecision(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load decisions";
      setErrorMessage(msg);
    } finally {
      setIsLoadingDecisions(false);
    }
  }, [urlDecisionId]);

  useEffect(() => {
    loadDecisionsList();
  }, [loadDecisionsList]);

  // Load active decision data
  const loadActiveDecisionData = useCallback(async (dec: DecisionRecord) => {
    setIsLoadingDetails(true);
    try {
      // 1. Fetch Decision Context in parallel with other entities
      const contextPromise = getDecisionContext(dec.product_id, dec.warehouse_id)
        .then((data) => setContext(data))
        .catch(() => setContext(null));

      // 2. Candidate Actions
      const actionsPromise = getCandidateActions(dec.id)
        .then((data) => setCandidateActions(data))
        .catch(() => setCandidateActions([]));

      // 3. Recommendation
      const recPromise = getDecisionRecommendation(dec.id)
        .then((data) => setRecommendation(data))
        .catch(() => setRecommendation(null));

      // 4. Validation Report
      const valPromise = getDecisionValidation(dec.id)
        .then((data) => setValidation(data))
        .catch(() => setValidation(null));

      // 5. Evidence Sheet
      const evPromise = getDecisionEvidenceSheet(dec.id, true)
        .then((data) => setEvidenceSheet(data))
        .catch(() => setEvidenceSheet(null));

      // 6. Provenance Trace
      const prvPromise = getDecisionProvenance(dec.id)
        .then((data) => setProvenance(data))
        .catch(() => setProvenance(null));

      // 7. Decision Replay
      const rplPromise = getDecisionReplay(dec.id)
        .then((data) => setReplay(data))
        .catch(() => setReplay(null));

      // 8. Scenarios
      const scnPromise = getDecisionScenarios(dec.id)
        .then((data) => setScenarios(data))
        .catch(() => setScenarios([]));

      // 9. Versions
      const verPromise = getDecisionVersions(dec.id)
        .then((data) => setVersions(data))
        .catch(() => setVersions([]));

      await Promise.allSettled([
        contextPromise,
        actionsPromise,
        recPromise,
        valPromise,
        evPromise,
        prvPromise,
        rplPromise,
        scnPromise,
        verPromise,
      ]);
    } catch {
      // Non-blocking fallback; individual panels represent missing/unavailable data accurately
    } finally {
      setIsLoadingDetails(false);
    }
  }, []);

  // Sync active decision whenever activeDecisionId changes
  useEffect(() => {
    if (!activeDecisionId || decisions.length === 0) return;
    const current = decisions.find((d) => d.id === activeDecisionId);
    if (current) {
      setActiveDecision(current);
      loadActiveDecisionData(current);
    }
  }, [activeDecisionId, decisions, loadActiveDecisionData]);

  // Handle switching decisions
  const handleSelectDecision = (decisionId: string) => {
    setActiveDecisionId(decisionId);
    router.push(`/decisions?id=${encodeURIComponent(decisionId)}`);
  };

  // Seed / Create demonstration decision if repository is empty
  const handleInitializeDemoDecision = async () => {
    setIsCreatingDecision(true);
    setErrorMessage(null);
    try {
      // 1. Create Decision
      const newDec = await createDecision({
        product_id: "prod-001",
        warehouse_id: "wh-001",
      });

      // 2. Create Candidate Actions: DO_NOTHING and PLACE_ORDER
      await createCandidateAction(newDec.id, {
        type: "DO_NOTHING",
        parameters: {},
        description: "Status quo baseline (do nothing)",
      });

      await createCandidateAction(newDec.id, {
        type: "PLACE_ORDER",
        parameters: { quantity: 60 },
        description: "Procure 60 units from Pacific Component Logistics",
      });

      // 3. Advance lifecycle to READY step-by-step
      const stages: DecisionStatus[] = [
        "CONTEXTUALIZING",
        "CONSTRUCTING",
        "VALIDATING",
        "EVALUATING",
        "READY",
      ];
      for (const st of stages) {
        try {
          await updateDecisionStatus(newDec.id, st);
        } catch {
          break;
        }
      }

      // 4. Reload decisions list and select this newly seeded decision
      await loadDecisionsList(newDec.id);
      router.push(`/decisions?id=${encodeURIComponent(newDec.id)}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to seed demo decision";
      setErrorMessage(msg);
    } finally {
      setIsCreatingDecision(false);
    }
  };

  // Create custom new decision
  const handleCreateCustomDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreatingDecision(true);
    setErrorMessage(null);
    try {
      const created = await createDecision({
        product_id: newProductId.trim(),
        warehouse_id: newWarehouseId.trim(),
      });
      setShowCreateModal(false);
      await loadDecisionsList(created.id);
      router.push(`/decisions?id=${encodeURIComponent(created.id)}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create decision";
      setErrorMessage(msg);
    } finally {
      setIsCreatingDecision(false);
    }
  };

  // Seed default candidate actions for current decision if empty
  const handleSeedDefaultActions = async () => {
    if (!activeDecision) return;
    try {
      await createCandidateAction(activeDecision.id, {
        type: "DO_NOTHING",
        parameters: {},
        description: "Maintain current inventory level",
      });
      await createCandidateAction(activeDecision.id, {
        type: "PLACE_ORDER",
        parameters: { quantity: 50 },
        description: "Place replenishment purchase order",
      });
      loadActiveDecisionData(activeDecision);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to register candidate actions";
      setErrorMessage(msg);
    }
  };

  return (
    <div className="edos-ws-page">
      {/* 1. Workspace Header with Decision Selector & Lifecycle Stepper */}
      <WorkspaceHeader
        decisions={decisions}
        activeDecision={activeDecision}
        onSelectDecision={handleSelectDecision}
        onCreateDecisionPrompt={() => setShowCreateModal(true)}
        isLoading={isLoadingDecisions || isLoadingDetails}
      />

      {/* Error Banner */}
      {errorMessage && (
        <div className="edos-alert edos-alert--danger" role="alert" style={{ margin: "16px 0" }}>
          {errorMessage}
        </div>
      )}

      {/* 2. Create Decision Modal / Drawer */}
      {showCreateModal && (
        <div className="edos-modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="edos-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-labelledby="modal-title">
            <h3 id="modal-title" style={{ marginBottom: "12px" }}>
              Create New Operational Decision Run
            </h3>
            <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
              Initializes a new identifiable decision record in initial <Badge variant="neutral">DRAFT</Badge> status.
            </p>

            <form onSubmit={handleCreateCustomDecision}>
              <div className="edos-form-group">
                <label htmlFor="modal-preset" className="edos-label">
                  Situation Preset:
                </label>
                <select
                  id="modal-preset"
                  className="edos-select"
                  onChange={(e) => {
                    const preset = PRESET_SITUATIONS.find((p) => p.productId === e.target.value);
                    if (preset) {
                      setNewProductId(preset.productId);
                      setNewWarehouseId(preset.warehouseId);
                    }
                  }}
                >
                  {PRESET_SITUATIONS.map((preset) => (
                    <option key={preset.id} value={preset.productId}>
                      {preset.label} — {preset.description}
                    </option>
                  ))}
                </select>
              </div>

              <div className="edos-ws-grid edos-ws-grid--2col" style={{ marginTop: "12px" }}>
                <div className="edos-form-group">
                  <label htmlFor="modal-product-id" className="edos-label">
                    Product Identifier:
                  </label>
                  <input
                    id="modal-product-id"
                    type="text"
                    className="edos-input"
                    value={newProductId}
                    onChange={(e) => setNewProductId(e.target.value)}
                    required
                  />
                </div>
                <div className="edos-form-group">
                  <label htmlFor="modal-warehouse-id" className="edos-label">
                    Warehouse Identifier:
                  </label>
                  <input
                    id="modal-warehouse-id"
                    type="text"
                    className="edos-input"
                    value={newWarehouseId}
                    onChange={(e) => setNewWarehouseId(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "20px" }}>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowCreateModal(false)}
                  disabled={isCreatingDecision}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={isCreatingDecision}>
                  {isCreatingDecision ? "Creating Decision..." : "Create Decision"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 3. Empty State (No decisions recorded in repo) */}
      {!isLoadingDecisions && decisions.length === 0 && (
        <div style={{ marginTop: "32px" }}>
          <EmptyState
            title="No Operational Decisions In System"
            description="The EDOS backend repository is ready. Initialize a demonstration decision with candidate actions and calculated recommendation to begin reviewer evaluation."
            action={
              <Button
                variant="primary"
                onClick={handleInitializeDemoDecision}
                disabled={isCreatingDecision}
              >
                {isCreatingDecision ? "Initializing Demo..." : "Initialize Demonstration Decision"}
              </Button>
            }
          />
        </div>
      )}

      {/* 4. Loaded Decision Reviewer Workspace */}
      {!isLoadingDecisions && activeDecision && (
        <div className="edos-ws-body">
          {/* Section Navigation Quick-Bar */}
          <nav className="edos-ws-nav-bar" aria-label="Workspace section tabs">
            {[
              { id: "all", label: "Unified Workspace View" },
              { id: "overview", label: "A. Overview & Context" },
              { id: "actions", label: "B. Recommended Action & Scenarios" },
              { id: "trust", label: "C. Evidence & Trust" },
              { id: "ai", label: "D. AI Explanation & Q&A" },
            ].map((sec) => (
              <button
                key={sec.id}
                type="button"
                className={`edos-ws-nav-btn ${activeSection === sec.id ? "edos-ws-nav-btn--active" : ""}`}
                onClick={() => setActiveSection(sec.id)}
              >
                {sec.label}
              </button>
            ))}
          </nav>

          {/* Section A: Decision Overview */}
          {(activeSection === "all" || activeSection === "overview") && (
            <div id="section-overview" style={{ marginBottom: "32px" }}>
              <DecisionOverviewSection
                decision={activeDecision}
                context={context}
                recommendation={recommendation}
                isLoadingContext={isLoadingDetails}
              />
            </div>
          )}

          {/* Section B: Recommended Action and Scenarios */}
          {(activeSection === "all" || activeSection === "actions") && (
            <div id="section-actions" style={{ marginBottom: "32px" }}>
              <RecommendedActionsScenariosSection
                decisionId={activeDecision.id}
                candidateActions={candidateActions}
                recommendation={recommendation}
                scenarios={scenarios}
                onRefreshScenarios={() => {
                  getDecisionScenarios(activeDecision.id)
                    .then((sc) => setScenarios(sc))
                    .catch(() => {});
                }}
                onSeedActionsPrompt={handleSeedDefaultActions}
                isLoading={isLoadingDetails}
              />
            </div>
          )}

          {/* Section C: Evidence and Decision Trust */}
          {(activeSection === "all" || activeSection === "trust") && (
            <div id="section-trust" style={{ marginBottom: "32px" }}>
              <EvidenceTrustSection
                decisionId={activeDecision.id}
                validation={validation}
                evidenceSheet={evidenceSheet}
                provenance={provenance}
                replay={replay}
                onRefreshReplay={() => {
                  getDecisionReplay(activeDecision.id)
                    .then((r) => setReplay(r))
                    .catch(() => {});
                }}
                onRevalidatePrompt={() => {
                  getDecisionValidation(activeDecision.id, true)
                    .then((v) => setValidation(v))
                    .catch(() => {});
                }}
                isLoading={isLoadingDetails}
              />
            </div>
          )}

          {/* Section D: AI Explanation and Decision Q&A */}
          {(activeSection === "all" || activeSection === "ai") && (
            <div id="section-ai" style={{ marginBottom: "32px" }}>
              <DecisionAISection
                decisionId={activeDecision.id}
                versionId={versions.length > 0 ? versions[0].id : null}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function DecisionWorkspacePage() {
  return (
    <Suspense
      fallback={
        <div style={{ padding: "48px 0" }}>
          <LoadingState
            label="Loading Decision Workspace..."
            sublabel="Connecting to operational decision systems and models"
          />
        </div>
      }
    >
      <DecisionWorkspaceContent />
    </Suspense>
  );
}
