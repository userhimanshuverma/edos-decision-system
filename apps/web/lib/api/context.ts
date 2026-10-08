/**
 * Decision Context API client layer.
 *
 * Provides strongly typed client methods for interacting with the
 * Day 9 FastAPI Context Engine endpoints:
 *   GET /api/context/product/{product_id}/warehouse/{warehouse_id}
 */

import type { DecisionContext } from "../types/context";

export class ContextApiError extends Error {
  statusCode: number;
  detail?: string;

  constructor(message: string, statusCode: number, detail?: string) {
    super(message);
    this.name = "ContextApiError";
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

/**
 * Resolves the operational API base URL for either server-side or browser execution.
 */
function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    // In browser, relative URL takes advantage of Next.js rewrites and eliminates CORS friction
    return "";
  }
  return (
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000"
  );
}

/**
 * Fetches the unified operational decision context for a given product and warehouse.
 *
 * @param productId Unique product identifier (e.g. 'prod-001')
 * @param warehouseId Unique warehouse identifier (e.g. 'wh-001')
 * @param supplierId Optional explicit supplier ID override
 */
export async function getDecisionContext(
  productId: string,
  warehouseId: string,
  supplierId?: string
): Promise<DecisionContext> {
  const normProductId = productId.trim();
  const normWarehouseId = warehouseId.trim();

  if (!normProductId || !normWarehouseId) {
    throw new ContextApiError(
      "Both Product ID and Warehouse ID must be provided.",
      400
    );
  }

  const baseUrl = getApiBaseUrl();
  const queryParam = supplierId ? `?supplier_id=${encodeURIComponent(supplierId.trim())}` : "";
  const endpoint = `${baseUrl}/api/context/product/${encodeURIComponent(normProductId)}/warehouse/${encodeURIComponent(normWarehouseId)}${queryParam}`;

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    });
  } catch (err: unknown) {
    const errorMsg =
      err instanceof Error ? err.message : "Network request failed";
    throw new ContextApiError(
      `Unable to reach EDOS Context Engine API: ${errorMsg}`,
      0
    );
  }

  if (!response.ok) {
    let detail = "";
    try {
      const errBody = await response.json();
      detail = typeof errBody.detail === "string" ? errBody.detail : JSON.stringify(errBody.detail);
    } catch {
      detail = response.statusText;
    }

    if (response.status === 404) {
      throw new ContextApiError(
        detail || `Situation context not found for product '${normProductId}' at warehouse '${normWarehouseId}'.`,
        404,
        detail
      );
    }

    throw new ContextApiError(
      detail || `Failed to fetch decision context (HTTP ${response.status})`,
      response.status,
      detail
    );
  }

  const data: DecisionContext = await response.json();
  return data;
}

/**
 * Deterministic ShopFlow reference catalog metadata for quick situation selection.
 */
export interface CatalogProduct {
  id: string;
  sku: string;
  name: string;
  category: string;
}

export interface CatalogWarehouse {
  id: string;
  code: string;
  name: string;
  location: string;
}

export const CATALOG_PRODUCTS: CatalogProduct[] = [
  { id: "prod-001", sku: "SKU-ELEC-1001", name: "Industrial IoT Gateway Edge-X", category: "Industrial Electronics" },
  { id: "prod-002", sku: "SKU-ELEC-1002", name: "Quad-Core Embedded Logic Controller", category: "Industrial Electronics" },
  { id: "prod-003", sku: "SKU-MECH-2001", name: "High-Torque Brushless Servo Motor", category: "Mechanical Automation" },
  { id: "prod-004", sku: "SKU-MECH-2002", name: "Precision Ground Ball Screw Assembly", category: "Mechanical Automation" },
  { id: "prod-005", sku: "SKU-POWR-3001", name: "24V 20A Industrial DIN-Rail PSU", category: "Power Systems" },
  { id: "prod-006", sku: "SKU-POWR-3002", name: "Modular LiFePO4 48V Storage Cell", category: "Power Systems" },
  { id: "prod-007", sku: "SKU-NETW-4001", name: "Managed 8-Port Gigabit Switch", category: "Networking & Telecom" },
  { id: "prod-008", sku: "SKU-NETW-4002", name: "Ruggedized Dual-SIM LTE Router", category: "Networking & Telecom" },
  { id: "prod-009", sku: "SKU-SENS-5001", name: "Infrared Thermal Line Scanner", category: "Sensors & Instrumentation" },
  { id: "prod-010", sku: "SKU-SENS-5002", name: "Triaxial Piezoelectric Vibration Sensor", category: "Sensors & Instrumentation" },
];

export const CATALOG_WAREHOUSES: CatalogWarehouse[] = [
  { id: "wh-001", code: "WH-EAST-01", name: "Eastern Logistics Hub", location: "Allentown, PA" },
  { id: "wh-002", code: "WH-CENT-02", name: "Midwest Distribution Center", location: "Chicago, IL" },
  { id: "wh-003", code: "WH-WEST-03", name: "Pacific Gateway Depot", location: "Reno, NV" },
];

export interface PresetSituation {
  id: string;
  label: string;
  productId: string;
  warehouseId: string;
  expectedStatus: string;
  description: string;
}

export const PRESET_SITUATIONS: PresetSituation[] = [
  {
    id: "default-attention",
    label: "SKU-ELEC-1001 @ Eastern Hub",
    productId: "prod-001",
    warehouseId: "wh-001",
    expectedStatus: "ATTENTION",
    description: "Moderate stock buffer, increasing demand trajectory (+14.7%)",
  },
  {
    id: "elec-controller-midwest",
    label: "SKU-ELEC-1002 @ Midwest DC",
    productId: "prod-002",
    warehouseId: "wh-002",
    expectedStatus: "ATTENTION / ELEVATED",
    description: "Embedded Logic Controller at Midwest Distribution Center",
  },
  {
    id: "servo-motor-east",
    label: "SKU-MECH-2001 @ Eastern Hub",
    productId: "prod-003",
    warehouseId: "wh-001",
    expectedStatus: "NORMAL",
    description: "High-torque servo with stable demand and reliable supplier",
  },
  {
    id: "power-supply-west",
    label: "SKU-POWR-3001 @ Pacific Depot",
    productId: "prod-005",
    warehouseId: "wh-003",
    expectedStatus: "ATTENTION",
    description: "24V DIN-Rail PSU inventory position at Pacific Gateway",
  },
];
