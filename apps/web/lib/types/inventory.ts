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
