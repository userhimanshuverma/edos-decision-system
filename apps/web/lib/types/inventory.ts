/**
 * Inventory operational state representation matching the Day 6 FastAPI schema.
 */
export interface InventoryRecord {
  inventory_id: string;
  id: string;
  product_id: string;
  warehouse_id: string;
  quantity_on_hand: number;
  quantity_reserved: number;
  available_quantity: number;
  reorder_point: number;
  updated_at: string;
}

/**
 * Supported replenishment policies matching Day 17 domain model.
 */
export type ReplenishmentPolicyType =
  | "REORDER_POINT_DEFICIT"
  | "LEAD_TIME_DEMAND"
  | "TARGET_STOCK";

/**
 * Detailed auditable calculation breakdown matching Day 17 schema.
 */
export interface ReplenishmentBreakdown {
  available_quantity: number;
  reorder_point: number;
  is_below_reorder: boolean;
  target_stock: number;
  net_deficit: number;
  gross_deficit: number;
  lead_time_days?: number | null;
  average_daily_demand?: number | null;
  lead_time_demand?: number | null;
  warehouse_capacity?: number | null;
  policy_notes: string[];
}

/**
 * Response model for replenishment calculation matching Day 17 API contract.
 */
export interface ReplenishmentResponse {
  product_id: string;
  warehouse_id: string;
  policy_type: ReplenishmentPolicyType;
  replenishment_quantity: number;
  is_replenishment_needed: boolean;
  available_quantity: number;
  target_stock: number;
  formula: string;
  breakdown: ReplenishmentBreakdown;
}

/**
 * Request payload for replenishment calculation.
 */
export interface CalculateReplenishmentRequest {
  product_id: string;
  warehouse_id: string;
  policy_type?: ReplenishmentPolicyType;
  target_stock?: number;
  supplier_id?: string;
  enforce_reorder_trigger?: boolean;
}

/**
 * Supported stockout risk calculation model types matching Day 18 domain.
 */
export type StockoutRiskModelType = "DETERMINISTIC_LEAD_TIME_EXPOSURE";

/**
 * Deterministic operational stockout risk classification levels matching Day 18 domain.
 */
export type StockoutRiskLevel =
  | "CRITICAL"
  | "HIGH"
  | "MEDIUM"
  | "LOW"
  | "NO_DEMAND";

/**
 * Detailed auditable calculation breakdown for stockout risk matching Day 18 schema.
 */
export interface StockoutRiskBreakdown {
  available_quantity: number;
  reorder_point: number;
  average_daily_demand: number;
  lead_time_days: number;
  coverage_days?: number | null;
  lead_time_demand: number;
  exposure_deficit: number;
  buffer_days?: number | null;
  exposure_index: number;
  is_below_reorder: boolean;
  demand_std_dev?: number | null;
  demand_coefficient_of_variation?: number | null;
  supplier_reliability?: number | null;
  calculation_notes: string[];
}

/**
 * Response model for stockout risk calculation matching Day 18 API contract.
 */
export interface StockoutRiskResponse {
  product_id: string;
  warehouse_id: string;
  model_type: StockoutRiskModelType;
  risk_level: StockoutRiskLevel;
  exposure_index: number;
  is_stockout_predicted: boolean;
  is_probability: boolean;
  formula: string;
  assumptions: string[];
  limitations: string[];
  breakdown: StockoutRiskBreakdown;
}

/**
 * Request payload for stockout risk calculation.
 */
export interface CalculateStockoutRiskRequest {
  product_id: string;
  warehouse_id: string;
  supplier_id?: string;
  model_type?: StockoutRiskModelType;
}

