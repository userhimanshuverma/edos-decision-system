/**
 * Demand operational state representations matching the Day 7 FastAPI schemas.
 */

export interface DemandRecord {
  demand_id: string;
  id: string;
  product_id: string;
  warehouse_id: string;
  date: string;
  quantity: number;
}

export interface DailyDemandPoint {
  date: string;
  quantity: number;
}

export interface DemandTrend {
  product_id: string;
  warehouse_id: string | null;
  total_demand: number;
  average_daily_demand: number;
  trend_direction: 'increasing' | 'decreasing' | 'stable';
  percentage_change: number;
  history: DailyDemandPoint[];
}
