"use client";

import React from "react";
import { CATALOG_PRODUCTS, CATALOG_WAREHOUSES, PRESET_SITUATIONS } from "../../lib/api/context";
import { Button } from "../ui/button";

export interface SituationSelectorProps {
  productId: string;
  warehouseId: string;
  onSelectSituation: (productId: string, warehouseId: string) => void;
  onRefresh: () => void;
  isLoading?: boolean;
}

export function SituationSelector({
  productId,
  warehouseId,
  onSelectSituation,
  onRefresh,
  isLoading = false,
}: SituationSelectorProps) {
  const handleProductChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onSelectSituation(e.target.value, warehouseId);
  };

  const handleWarehouseChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onSelectSituation(productId, e.target.value);
  };

  return (
    <div className="edos-situation-selector-bar">
      <div className="edos-situation-selector-bar__main">
        <div className="edos-situation-selector-group">
          <label htmlFor="situation-product-select" className="edos-situation-selector-label">
            Target Product
          </label>
          <div className="edos-select-wrapper">
            <select
              id="situation-product-select"
              value={productId}
              onChange={handleProductChange}
              disabled={isLoading}
              className="edos-select edos-select--compact"
            >
              {CATALOG_PRODUCTS.map((prod) => (
                <option key={prod.id} value={prod.id}>
                  {prod.sku} — {prod.name}
                </option>
              ))}
            </select>
            <span className="edos-select-chevron" aria-hidden="true">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </span>
          </div>
        </div>

        <div className="edos-situation-selector-group">
          <label htmlFor="situation-warehouse-select" className="edos-situation-selector-label">
            Target Warehouse
          </label>
          <div className="edos-select-wrapper">
            <select
              id="situation-warehouse-select"
              value={warehouseId}
              onChange={handleWarehouseChange}
              disabled={isLoading}
              className="edos-select edos-select--compact"
            >
              {CATALOG_WAREHOUSES.map((wh) => (
                <option key={wh.id} value={wh.id}>
                  {wh.code} — {wh.name} ({wh.location})
                </option>
              ))}
            </select>
            <span className="edos-select-chevron" aria-hidden="true">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </span>
          </div>
        </div>

        <div className="edos-situation-selector-actions">
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isLoading}
            title="Reload context data from API"
          >
            <span className="edos-situation-refresh-icon" aria-hidden="true">
              ↻
            </span>
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      <div className="edos-situation-presets">
        <span className="edos-situation-presets__label">Presets:</span>
        <div className="edos-situation-presets__chips">
          {PRESET_SITUATIONS.map((preset) => {
            const isSelected =
              preset.productId === productId && preset.warehouseId === warehouseId;
            return (
              <button
                key={preset.id}
                type="button"
                className={`edos-situation-preset-chip ${
                  isSelected ? "edos-situation-preset-chip--active" : ""
                }`}
                onClick={() => onSelectSituation(preset.productId, preset.warehouseId)}
                disabled={isLoading}
                title={preset.description}
              >
                <span>{preset.label}</span>
                <span className="edos-situation-preset-chip__status">
                  {preset.expectedStatus}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
