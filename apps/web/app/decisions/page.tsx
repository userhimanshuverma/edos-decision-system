"use client";

import React, { useEffect, useState, useCallback, useRef, Suspense } from "react";
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
  SectionLoadStatus,
  SectionErrorState,
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
  DecisionApiError,
} from "../../lib/api/decision";
import { getDecisionContext, PRESET_SITUATIONS } from "../../lib/api/context";

import { WorkspaceHeader } from "../../components/workspace/workspace-header";
import { DecisionOverviewSection } from "../../components/workspace/decision-overview-section";
import { RecommendedActionsScenariosSection } from "../../components/workspace/recommended-actions-scenarios-section";
import { EvidenceTrustSection } from "../../components/workspace/evidence-trust-section";
import { DecisionAISection } from "../../components/workspace/decision-ai-section";

import { LoadingState } from "../../components/ui/loading-state";
import { EmptyState } from "../../components/ui/empty-state";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";

function parseErrorState(err: unknown, fallbackMessage: string): SectionErrorState {
  if (err instanceof DecisionApiError) {
    return {
      message: err.message,
      errorCode: err.errorCode,
      category: err.category,
      statusCode: err.statusCode,
      isRetryable: err.isRetryable,
    };
  }
  if (err instanceof Error) {
    return {
      message: err.message,
      isRetryable: true,
    };
  }
  return {
    message: fallbackMessage,
    isRetryable: true,
  };
}

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
  const [contextStatus, setContextStatus] = useState<SectionLoadStatus>("idle");
  const [contextError, setContextError] = useState<SectionErrorState | null>(null);

  const [candidateActions, setCandidateActions] = useState<CandidateActionRecord[]>([]);
  const [actionsStatus, setActionsStatus] = useState<SectionLoadStatus>("idle");
  const [actionsError, setActionsError] = useState<SectionErrorState | null>(null);

  const [recommendation, setRecommendation] = useState<RecommendationRecord | null>(null);
  const [recommendationStatus, setRecommendationStatus] = useState<SectionLoadStatus>("idle");
  const [recommendationError, setRecommendationError] = useState<SectionErrorState | null>(null);

  const [validation, setValidation] = useState<DecisionValidationRecord | null>(null);
  const [validationStatus, setValidationStatus] = useState<SectionLoadStatus>("idle");
  const [validationError, setValidationError] = useState<SectionErrorState | null>(null);

  const [evidenceSheet, setEvidenceSheet] = useState<DecisionEvidenceSheetRecord | null>(null);
  const [evidenceStatus, setEvidenceStatus] = useState<SectionLoadStatus>("idle");
  const [evidenceError, setEvidenceError] = useState<SectionErrorState | null>(null);

  const [provenance, setProvenance] = useState<DecisionProvenanceTraceRecord | null>(null);
  const [provenanceStatus, setProvenanceStatus] = useState<SectionLoadStatus>("idle");
  const [provenanceError, setProvenanceError] = useState<SectionErrorState | null>(null);

  const [replay, setReplay] = useState<DecisionReplayRecord | null>(null);
  const [replayStatus, setReplayStatus] = useState<SectionLoadStatus>("idle");
  const [replayErrorState, setReplayErrorState] = useState<SectionErrorState | null>(null);

  const [scenarios, setScenarios] = useState<DecisionScenarioRecord[]>([]);
  const [scenariosStatus, setScenariosStatus] = useState<SectionLoadStatus>("idle");
  const [scenariosError, setScenariosError] = useState<SectionErrorState | null>(null);

  const [versions, setVersions] = useState<DecisionVersionRecord[]>([]);
  const [versionsStatus, setVersionsStatus] = useState<SectionLoadStatus>("idle");
  const [versionsError, setVersionsError] = useState<SectionErrorState | null>(null);

  // Overall state indicators
  const [isLoadingDecisions, setIsLoadingDecisions] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // New decision creation modal/bar state
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newProductId, setNewProductId] = useState<string>("prod-001");
  const [newWarehouseId, setNewWarehouseId] = useState<string>("wh-001");
  const [isCreatingDecision, setIsCreatingDecision] = useState<boolean>(false);
  const [isSeedingActions, setIsSeedingActions] = useState<boolean>(false);

  // View section focus filter (all or specific tab)
  const [activeSection, setActiveSection] = useState<string>("all");

  // Sequence ref to prevent out-of-order response race conditions when switching decisions
  const requestSeqRef = useRef<number>(0);

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
      const parsed = parseErrorState(err, "Failed to load decisions list");
      setErrorMessage(parsed.message);
    } finally {
      setIsLoadingDecisions(false);
    }
  }, [urlDecisionId]);

  useEffect(() => {
    loadDecisionsList();
  }, [loadDecisionsList]);

  // Load active decision data with isolated error handling & race condition guard
  const loadActiveDecisionData = useCallback(async (dec: DecisionRecord) => {
    const currentSeq = ++requestSeqRef.current;

    // Reset statuses to loading and clear errors
    setContextStatus("loading");
    setContextError(null);

    setActionsStatus("loading");
    setActionsError(null);

    setRecommendationStatus("loading");
    setRecommendationError(null);

    setValidationStatus("loading");
    setValidationError(null);

    setEvidenceStatus("loading");
    setEvidenceError(null);

    setProvenanceStatus("loading");
    setProvenanceError(null);

    setReplayStatus("loading");
    setReplayErrorState(null);

    setScenariosStatus("loading");
    setScenariosError(null);

    setVersionsStatus("loading");
    setVersionsError(null);

    // 1. Fetch Decision Context
    const contextPromise = getDecisionContext(dec.product_id, dec.warehouse_id)
      .then((data) => {
        if (currentSeq !== requestSeqRef.current) return;
        setContext(data);
        setContextStatus("success");
      })
      .catch((err) => {
        if (currentSeq !== requestSeqRef.current) return;
        setContext(null);
        setContextError(parseErrorState(err, "Unable to load operational context"));
        setContextStatus("error");
      });

    // 2. Candidate Actions
    const actionsPromise = getCandidateActions(dec.id)
      .then((data) => {
        if (currentSeq !== requestSeqRef.current) return;
        setCandidateActions(data);
        setActionsStatus(data.length === 0 ? "empty" : "success");
      })
      .catch((err) => {
        if (currentSeq !== requestSeqRef.current) return;
        setCandidateActions([]);
        setActionsError(parseErrorState(err, "Unable to load candidate actions"));
        setActionsStatus("error");
      });

    // 3. Recommendation
    const recPromise = getDecisionRecommendation(dec.id)
      .then((data) => {
        if (currentSeq !== requestSeqRef.current) return;
        setRecommendation(data);
        setRecommendationStatus(data ? "success" : "empty");
      })
      .catch((err) => {
        if (currentSeq !== requestSeqRef.current) return;
        setRecommendation(null);
        setRecommendationError(parseErrorState(err, "Unable to compute recommendation"));
        setRecommendationStatus("error");
      });

    // 4. Validation Report
    const valPromise = getDecisionValidation(dec.id)
      .then((data) => {
        if (currentSeq !== requestSeqRef.current) return;
        setValidation(data);
        setValidationStatus(data ? "success" : "empty");
      })
      .catch((err) => {
        if (currentSeq !== requestSeqRef.current) return;
        setValidation(null);
        setValidationError(parseErrorState(err, "Unable to load validation report"));
        setValidationStatus("error");
      });

    // 5. Evidence Sheet
    const evPromise = getDecisionEvidenceSheet(dec.id, true)
      .then((data) => {
        if (currentSeq !== requestSeqRef.current) return;
        setEvidenceSheet(data);
        setEvidenceStatus(data ? "success" : "empty");
      })
      .catch((err) => {
        if (currentSeq !== requestSeqRef.current) return;
        setEvidenceSheet(null);
        setEvidenceError(parseErrorState(err, "Unable to load evidence sheet"));
        setEvidenceStatus("error");
      });

    // 6. Provenance Trace
    const prvPromise = getDecisionProvenance(dec.id)
      .then((data) => {
        if (currentSeq !== requestSeqRef.current) return;
        setProvenance(data);
        setProvenanceStatus(data ? "success" : "empty");
      })
      .catch((err) => {
        if (currentSeq !== requestSeqRef.current) return;
        setProvenance(null);
        setProvenanceError(parseErrorState(err, "Unable to load provenance trace"));
        setProvenanceStatus("error");
      });

    // 7. Decision Replay
    const rplPromise = getDecisionReplay(dec.id)
      .then((data) => {
        if (currentSeq !== requestSeqRef.current) return;
        setReplay(data);
        setReplayStatus(data ? "success" : "empty");
      })
      .catch((err) => {
        if (currentSeq !== requestSeqRef.current) return;
        setReplay(null);
        setReplayErrorState(parseErrorState(err, "Unable to load replay record"));
        setReplayStatus("error");
      });

    // 8. Scenarios
    const scnPromise = getDecisionScenarios(dec.id)
      .then((data) => {
        if (currentSeq !== requestSeqRef.current) return;
        setScenarios(data);
        setScenariosStatus(data.length === 0 ? "empty" : "success");
      })
      .catch((err) => {
        if (currentSeq !== requestSeqRef.current) return;
        setScenarios([]);
        setScenariosError(parseErrorState(err, "Unable to load scenarios"));
        setScenariosStatus("error");
      });

    // 9. Versions
    const verPromise = getDecisionVersions(dec.id)
      .then((data) => {
        if (currentSeq !== requestSeqRef.current) return;
        setVersions(data);
        setVersionsStatus(data.length === 0 ? "empty" : "success");
      })
      .catch((err) => {
        if (currentSeq !== requestSeqRef.current) return;
        setVersions([]);
        setVersionsError(parseErrorState(err, "Unable to load versions"));
        setVersionsStatus("error");
      });

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

  // Safe retry handlers for independent workspace sections
  const handleRetryContext = useCallback(async () => {
    if (!activeDecision) return;
    setContextStatus("loading");
    setContextError(null);
    try {
      const data = await getDecisionContext(activeDecision.product_id, activeDecision.warehouse_id);
      setContext(data);
      setContextStatus("success");
    } catch (err: unknown) {
      setContextError(parseErrorState(err, "Unable to load operational context"));
      setContextStatus("error");
    }
  }, [activeDecision]);

  const handleRetryActions = useCallback(async () => {
    if (!activeDecision) return;
    setActionsStatus("loading");
    setActionsError(null);
    try {
      const data = await getCandidateActions(activeDecision.id);
      setCandidateActions(data);
      setActionsStatus(data.length === 0 ? "empty" : "success");
    } catch (err: unknown) {
      setActionsError(parseErrorState(err, "Unable to load candidate actions"));
      setActionsStatus("error");
    }
  }, [activeDecision]);

  const handleRetryRecommendation = useCallback(async () => {
    if (!activeDecision) return;
    setRecommendationStatus("loading");
    setRecommendationError(null);
    try {
      const data = await getDecisionRecommendation(activeDecision.id);
      setRecommendation(data);
      setRecommendationStatus(data ? "success" : "empty");
    } catch (err: unknown) {
      setRecommendationError(parseErrorState(err, "Unable to compute recommendation"));
      setRecommendationStatus("error");
    }
  }, [activeDecision]);

  const handleRetryValidation = useCallback(async () => {
    if (!activeDecision) return;
    setValidationStatus("loading");
    setValidationError(null);
    try {
      const data = await getDecisionValidation(activeDecision.id, true);
      setValidation(data);
      setValidationStatus(data ? "success" : "empty");
    } catch (err: unknown) {
      setValidationError(parseErrorState(err, "Unable to load validation report"));
      setValidationStatus("error");
    }
  }, [activeDecision]);

  const handleRetryEvidence = useCallback(async () => {
    if (!activeDecision) return;
    setEvidenceStatus("loading");
    setEvidenceError(null);
    try {
      const data = await getDecisionEvidenceSheet(activeDecision.id, true);
      setEvidenceSheet(data);
      setEvidenceStatus(data ? "success" : "empty");
    } catch (err: unknown) {
      setEvidenceError(parseErrorState(err, "Unable to load evidence sheet"));
      setEvidenceStatus("error");
    }
  }, [activeDecision]);

  const handleRetryProvenance = useCallback(async () => {
    if (!activeDecision) return;
    setProvenanceStatus("loading");
    setProvenanceError(null);
    try {
      const data = await getDecisionProvenance(activeDecision.id);
      setProvenance(data);
      setProvenanceStatus(data ? "success" : "empty");
    } catch (err: unknown) {
      setProvenanceError(parseErrorState(err, "Unable to load provenance trace"));
      setProvenanceStatus("error");
    }
  }, [activeDecision]);

  const handleRetryReplay = useCallback(async () => {
    if (!activeDecision) return;
    setReplayStatus("loading");
    setReplayErrorState(null);
    try {
      const data = await getDecisionReplay(activeDecision.id);
      setReplay(data);
      setReplayStatus(data ? "success" : "empty");
    } catch (err: unknown) {
      setReplayErrorState(parseErrorState(err, "Unable to load replay record"));
      setReplayStatus("error");
    }
  }, [activeDecision]);

  const handleRetryScenarios = useCallback(async () => {
    if (!activeDecision) return;
    setScenariosStatus("loading");
    setScenariosError(null);
    try {
      const data = await getDecisionScenarios(activeDecision.id);
      setScenarios(data);
      setScenariosStatus(data.length === 0 ? "empty" : "success");
    } catch (err: unknown) {
      setScenariosError(parseErrorState(err, "Unable to load scenarios"));
      setScenariosStatus("error");
    }
  }, [activeDecision]);

  // Seed / Create demonstration decision if repository is empty
  const handleInitializeDemoDecision = async () => {
    if (isCreatingDecision) return;
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
      const parsed = parseErrorState(err, "Failed to seed demo decision");
      setErrorMessage(parsed.message);
    } finally {
      setIsCreatingDecision(false);
    }
  };

  // Create custom new decision
  const handleCreateCustomDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isCreatingDecision) return;
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
      const parsed = parseErrorState(err, "Failed to create decision");
      setErrorMessage(parsed.message);
    } finally {
      setIsCreatingDecision(false);
    }
  };

  // Seed default candidate actions for current decision if empty
  const handleSeedDefaultActions = async () => {
    if (!activeDecision || isSeedingActions) return;
    setIsSeedingActions(true);
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
      const parsed = parseErrorState(err, "Failed to register candidate actions");
      setErrorMessage(parsed.message);
    } finally {
      setIsSeedingActions(false);
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
        isLoading={isLoadingDecisions}
      />

      {/* Global Error Notice if decision list fails */}
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
                contextStatus={contextStatus}
                contextError={contextError}
                onRetryContext={handleRetryContext}
                recommendation={recommendation}
                recommendationStatus={recommendationStatus}
                recommendationError={recommendationError}
                onRetryRecommendation={handleRetryRecommendation}
                isLoadingContext={contextStatus === "loading"}
              />
            </div>
          )}

          {/* Section B: Recommended Action and Scenarios */}
          {(activeSection === "all" || activeSection === "actions") && (
            <div id="section-actions" style={{ marginBottom: "32px" }}>
              <RecommendedActionsScenariosSection
                decisionId={activeDecision.id}
                candidateActions={candidateActions}
                actionsStatus={actionsStatus}
                actionsError={actionsError}
                onRetryActions={handleRetryActions}
                recommendation={recommendation}
                scenarios={scenarios}
                scenariosStatus={scenariosStatus}
                scenariosError={scenariosError}
                onRefreshScenarios={() => {
                  getDecisionScenarios(activeDecision.id)
                    .then((sc) => {
                      setScenarios(sc);
                      setScenariosStatus(sc.length === 0 ? "empty" : "success");
                    })
                    .catch((err) => {
                      setScenariosError(parseErrorState(err, "Failed to refresh scenarios"));
                      setScenariosStatus("error");
                    });
                }}
                onRetryScenarios={handleRetryScenarios}
                onSeedActionsPrompt={handleSeedDefaultActions}
                isLoading={actionsStatus === "loading"}
              />
            </div>
          )}

          {/* Section C: Evidence and Decision Trust */}
          {(activeSection === "all" || activeSection === "trust") && (
            <div id="section-trust" style={{ marginBottom: "32px" }}>
              <EvidenceTrustSection
                decisionId={activeDecision.id}
                validation={validation}
                validationStatus={validationStatus}
                validationError={validationError}
                onRetryValidation={handleRetryValidation}
                evidenceSheet={evidenceSheet}
                evidenceStatus={evidenceStatus}
                evidenceError={evidenceError}
                onRetryEvidence={handleRetryEvidence}
                provenance={provenance}
                provenanceStatus={provenanceStatus}
                provenanceError={provenanceError}
                onRetryProvenance={handleRetryProvenance}
                replay={replay}
                replayStatus={replayStatus}
                replayErrorState={replayErrorState}
                onRetryReplay={handleRetryReplay}
                onRefreshReplay={() => {
                  getDecisionReplay(activeDecision.id)
                    .then((r) => {
                      setReplay(r);
                      setReplayStatus(r ? "success" : "empty");
                    })
                    .catch((err) => {
                      setReplayErrorState(parseErrorState(err, "Failed to refresh replay record"));
                      setReplayStatus("error");
                    });
                }}
                onRevalidatePrompt={() => {
                  getDecisionValidation(activeDecision.id, true)
                    .then((v) => {
                      setValidation(v);
                      setValidationStatus(v ? "success" : "empty");
                    })
                    .catch((err) => {
                      setValidationError(parseErrorState(err, "Failed to revalidate constraints"));
                      setValidationStatus("error");
                    });
                }}
                isLoading={validationStatus === "loading"}
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
