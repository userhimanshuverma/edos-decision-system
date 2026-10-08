"use client";

import React, { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { DecisionContext } from "../../lib/types/context";
import {
  getDecisionContext,
  ContextApiError,
  PRESET_SITUATIONS,
} from "../../lib/api/context";
import { ContextHeader } from "../../components/context/context-header";
import { OperationalSnapshot } from "../../components/context/operational-snapshot";
import { InventoryPositionCard } from "../../components/context/inventory-position-card";
import { DemandHistoryChart } from "../../components/context/demand-history-chart";
import { SupplierContextCard } from "../../components/context/supplier-context-card";
import { ContextSummaryCard } from "../../components/context/context-summary-card";
import { SituationSelector } from "../../components/context/situation-selector";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorState } from "../../components/ui/error-state";
import { EmptyState } from "../../components/ui/empty-state";
import { Button } from "../../components/ui/button";

function ContextContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  // Extract initial product and warehouse from query params or default preset
  const paramProductId = searchParams?.get("product_id") || "prod-001";
  const paramWarehouseId = searchParams?.get("warehouse_id") || "wh-001";

  const [productId, setProductId] = useState<string>(paramProductId);
  const [warehouseId, setWarehouseId] = useState<string>(paramWarehouseId);
  const [contextData, setContextData] = useState<DecisionContext | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | undefined>(undefined);

  // Sync state if URL search parameters change externally
  useEffect(() => {
    const urlProd = searchParams?.get("product_id");
    const urlWh = searchParams?.get("warehouse_id");
    if (urlProd && urlProd !== productId) {
      setProductId(urlProd);
    }
    if (urlWh && urlWh !== warehouseId) {
      setWarehouseId(urlWh);
    }
  }, [searchParams, productId, warehouseId]);

  const loadContext = useCallback(
    async (pId: string, wId: string) => {
      setIsLoading(true);
      setErrorMessage(null);
      setErrorCode(undefined);

      try {
        const data = await getDecisionContext(pId, wId);
        setContextData(data);
      } catch (err: unknown) {
        if (err instanceof ContextApiError) {
          setErrorMessage(err.message);
          setErrorCode(`HTTP_${err.statusCode}`);
        } else if (err instanceof Error) {
          setErrorMessage(err.message);
          setErrorCode("CLIENT_EXCEPTION");
        } else {
          setErrorMessage("Failed to load decision context from API.");
          setErrorCode("UNKNOWN_ERROR");
        }
        setContextData(null);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    loadContext(productId, warehouseId);
  }, [productId, warehouseId, loadContext]);

  const handleSelectSituation = (newProdId: string, newWhId: string) => {
    setProductId(newProdId);
    setWarehouseId(newWhId);
    // Update browser URL query params without full page reload
    router.replace(`/context?product_id=${encodeURIComponent(newProdId)}&warehouse_id=${encodeURIComponent(newWhId)}`);
  };

  const handleResetToDefault = () => {
    const defaultPreset = PRESET_SITUATIONS[0];
    handleSelectSituation(defaultPreset.productId, defaultPreset.warehouseId);
  };

  return (
    <div className="edos-context-page">
      {/* 1. Situation Selector Bar */}
      <SituationSelector
        productId={productId}
        warehouseId={warehouseId}
        onSelectSituation={handleSelectSituation}
        onRefresh={() => loadContext(productId, warehouseId)}
        isLoading={isLoading}
      />

      {/* 2. Loading State */}
      {isLoading && (
        <div className="edos-context-loading-area" aria-live="polite">
          <LoadingState
            label="Synthesizing Decision Context..."
            sublabel={`Aggregating Product ${productId} @ Warehouse ${warehouseId} via Day 9 Context API`}
          />
          <div className="edos-skeleton-grid">
            <div className="edos-skeleton edos-skeleton--header-block" />
            <div className="edos-metrics-grid">
              <div className="edos-skeleton edos-skeleton--metric-card" />
              <div className="edos-skeleton edos-skeleton--metric-card" />
              <div className="edos-skeleton edos-skeleton--metric-card" />
            </div>
            <div className="edos-context-details-layout">
              <div className="edos-skeleton edos-skeleton--large-card" />
              <div className="edos-skeleton edos-skeleton--large-card" />
            </div>
          </div>
        </div>
      )}

      {/* 3. Error State */}
      {!isLoading && errorMessage && (
        <div className="edos-context-error-area">
          <ErrorState
            title="Operational Situation Not Found or Unreachable"
            message={errorMessage}
            code={errorCode}
            onRetry={() => loadContext(productId, warehouseId)}
            retryLabel="Retry Context Ingestion"
          />
          <div className="edos-context-error-actions">
            <Button variant="secondary" onClick={handleResetToDefault}>
              Reset to Primary Situation (SKU-ELEC-1001 @ Eastern Hub)
            </Button>
          </div>
        </div>
      )}

      {/* 4. Empty State */}
      {!isLoading && !errorMessage && !contextData && (
        <EmptyState
          title="No Decision Context Loaded"
          description="Select an operational product SKU and warehouse from the selector bar above to inspect situation data."
          action={
            <Button variant="primary" onClick={handleResetToDefault}>
              Open Default Situation
            </Button>
          }
        />
      )}

      {/* 5. Successfully Loaded Decision Context Screen */}
      {!isLoading && !errorMessage && contextData && (
        <div className="edos-context-content">
          {/* Section A: Page Header / Situation Identity */}
          <ContextHeader context={contextData} />

          {/* Section B: Operational Snapshot (4 pillars) */}
          <OperationalSnapshot context={contextData} />

          {/* Section C, D, E, F: Detailed Operational Views */}
          <div className="edos-context-details-layout">
            {/* Primary Column: Inventory & Observed Demand */}
            <div className="edos-context-details-column edos-context-details-column--primary">
              {/* Section C: Inventory Position */}
              <InventoryPositionCard context={contextData} />

              {/* Section D: Historical Demand Behavior */}
              <DemandHistoryChart demand={contextData.demand} />
            </div>

            {/* Secondary Column: Supplier & Deterministic Summary */}
            <div className="edos-context-details-column edos-context-details-column--secondary">
              {/* Section F: Deterministic Context Summary */}
              <ContextSummaryCard context={contextData} />

              {/* Section E: Supplier Context */}
              <SupplierContextCard context={contextData} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DecisionContextPage() {
  return (
    <Suspense
      fallback={
        <div className="edos-context-loading-area">
          <LoadingState
            label="Initializing Decision Context..."
            sublabel="Loading URL parameters and runtime context"
          />
        </div>
      }
    >
      <ContextContent />
    </Suspense>
  );
}
