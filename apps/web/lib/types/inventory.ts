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
