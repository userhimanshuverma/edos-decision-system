/**
 * Supplier operational state and risk context representations matching the Day 8 FastAPI schemas.
 */

export type SupplierRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface SupplierRecord {
  supplier_id: string;
  id: string;
  code: string;
  name: string;
  lead_time_days: number;
  reliability: number;
  active: boolean;
  risk_level: SupplierRiskLevel;
}

export interface SupplierRisk {
  supplier_id: string;
  code: string;
  lead_time_days: number;
  reliability: number;
  risk_level: SupplierRiskLevel;
}
