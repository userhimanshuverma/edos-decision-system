/**
 * Decision Context operational state representations matching the Day 9 FastAPI schemas.
 *
 * Provides strongly typed contracts for the unified operational snapshot
 * aggregating Product, Warehouse, Inventory, Demand, and Supplier dimensions.
 */

import { DailyDemandPoint } from './demand';
import { SupplierRiskLevel } from './supplier';

export type ContextStatus = 'NORMAL' | 'ATTENTION' | 'ELEVATED';

export interface ProductContext {
  id: string;
  sku: string;
  name: string;
  category: string;
  unit_cost: number;
  selling_price: number;
  reorder_point: number;
  active: boolean;
}

export interface WarehouseContext {
  id: string;
  code: string;
  name: string;
  location: string;
  capacity: number;
  active: boolean;
}

export interface InventoryContext {
  inventory_id: string | null;
  quantity_on_hand: number;
  quantity_reserved: number;
  available_quantity: number;
  reorder_point: number;
  updated_at: string | null;
}

export interface DailyDemandContextPoint {
  date: string;
  quantity: number;
}

export interface DemandContext {
  total_demand: number;
  average_daily_demand: number;
  trend_direction: 'increasing' | 'decreasing' | 'stable';
  percentage_change: number;
  window_days: number;
  history: DailyDemandPoint[];
}

export interface SupplierContext {
  supplier_id: string;
  code: string;
  name: string;
  lead_time_days: number;
  reliability: number;
  active: boolean;
  risk_level: SupplierRiskLevel;
}

export interface DerivedContextMetrics {
  coverage_days: number | null;
  lead_time_days: number | null;
  is_below_reorder: boolean;
  net_deficit: number;
  context_status: ContextStatus;
}

export interface DecisionContext {
  product_id: string;
  warehouse_id: string;
  product: ProductContext;
  warehouse: WarehouseContext;
  inventory: InventoryContext | null;
  demand: DemandContext | null;
  supplier: SupplierContext | null;
  metrics: DerivedContextMetrics;
  status: ContextStatus;
}

export type DecisionContextResponse = DecisionContext;
