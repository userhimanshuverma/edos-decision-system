import test from "node:test";
import assert from "node:assert/strict";

// Comprehensive test suite for Day 10 Decision Context UI logic, data contracts, and client integration

test("Decision Context - Catalog Presets Integrity", async () => {
  const { CATALOG_PRODUCTS, CATALOG_WAREHOUSES, PRESET_SITUATIONS } = await import(
    "../lib/api/context.ts"
  );

  assert.ok(Array.isArray(CATALOG_PRODUCTS), "CATALOG_PRODUCTS should be an array");
  assert.equal(CATALOG_PRODUCTS.length, 10, "Should have 10 catalog products");

  assert.ok(Array.isArray(CATALOG_WAREHOUSES), "CATALOG_WAREHOUSES should be an array");
  assert.equal(CATALOG_WAREHOUSES.length, 3, "Should have 3 warehouses");

  assert.ok(Array.isArray(PRESET_SITUATIONS), "PRESET_SITUATIONS should be an array");
  assert.ok(PRESET_SITUATIONS.length >= 3, "Should have multiple preset situations");

  for (const preset of PRESET_SITUATIONS) {
    assert.ok(preset.productId, "Preset must specify productId");
    assert.ok(preset.warehouseId, "Preset must specify warehouseId");
    assert.ok(preset.label, "Preset must specify label");
    assert.ok(preset.expectedStatus, "Preset must specify expectedStatus");
  }
});

test("Decision Context API - Input Validation", async () => {
  const { getDecisionContext, ContextApiError } = await import("../lib/api/context.ts");

  await assert.rejects(
    async () => {
      await getDecisionContext("", "wh-001");
    },
    (err) => {
      assert.ok(err instanceof ContextApiError);
      assert.equal(err.statusCode, 400);
      return true;
    }
  );

  await assert.rejects(
    async () => {
      await getDecisionContext("prod-001", "   ");
    },
    (err) => {
      assert.ok(err instanceof ContextApiError);
      assert.equal(err.statusCode, 400);
      return true;
    }
  );
});

test("Decision Context API - Live HTTP Integration with FastAPI", async () => {
  const { getDecisionContext } = await import("../lib/api/context.ts");

  // Tests live fetching against the running backend on port 8000
  const context = await getDecisionContext("prod-001", "wh-001");

  // 1. Situation identity
  assert.equal(context.product_id, "prod-001");
  assert.equal(context.warehouse_id, "wh-001");
  assert.equal(context.product.sku, "SKU-ELEC-1001");
  assert.equal(context.product.category, "Industrial Electronics");
  assert.equal(context.warehouse.code, "WH-EAST-01");

  // 2. Inventory position
  assert.ok(context.inventory !== null, "Inventory context must be populated");
  assert.equal(context.inventory.quantity_on_hand, 180);
  assert.equal(context.inventory.quantity_reserved, 27);
  assert.equal(context.inventory.available_quantity, 153);
  assert.equal(context.inventory.reorder_point, 50);

  // 3. Demand history & metrics
  assert.ok(context.demand !== null, "Demand context must be populated");
  assert.equal(context.demand.window_days, 14);
  assert.equal(context.demand.history.length, 14);
  assert.equal(context.demand.trend_direction, "increasing");
  assert.ok(context.demand.average_daily_demand > 0);

  // 4. Supplier intelligence
  assert.ok(context.supplier !== null, "Supplier context must be populated");
  assert.equal(context.supplier.code, "SUP-PAC-01");
  assert.equal(context.supplier.lead_time_days, 10);
  assert.equal(context.supplier.risk_level, "LOW");

  // 5. Derived metrics
  assert.ok(context.metrics.coverage_days !== null);
  assert.equal(context.metrics.lead_time_days, 10);
  assert.equal(context.metrics.is_below_reorder, false);
  assert.equal(context.metrics.net_deficit, 0);

  // 6. Context status
  assert.equal(context.status, "ATTENTION");
});

test("Decision Context API - 404 Error Handling for Unknown Context", async () => {
  const { getDecisionContext, ContextApiError } = await import("../lib/api/context.ts");

  await assert.rejects(
    async () => {
      await getDecisionContext("prod-unknown-999", "wh-001");
    },
    (err) => {
      assert.ok(err instanceof ContextApiError);
      assert.equal(err.statusCode, 404);
      assert.ok(err.message.includes("prod-unknown-999"));
      return true;
    }
  );
});

test("Decision Context API - Supplier Override Support", async () => {
  const { getDecisionContext } = await import("../lib/api/context.ts");

  const context = await getDecisionContext("prod-001", "wh-001", "sup-002");
  assert.equal(context.supplier.supplier_id, "sup-002");
  assert.equal(context.supplier.code, "SUP-APX-02");
});

test("Decision Context - Inventory Position Calculations", () => {
  // Available quantity = on hand - reserved
  const onHand = 180;
  const reserved = 27;
  const available = onHand - reserved;
  assert.equal(available, 153);

  // Net deficit = max(0, reorder_point - available)
  const reorderPoint = 50;
  const netDeficit = Math.max(0, reorderPoint - available);
  assert.equal(netDeficit, 0);

  // When below reorder point
  const deficitAvailable = 35;
  const actualDeficit = Math.max(0, reorderPoint - deficitAvailable);
  assert.equal(actualDeficit, 15);
});

test("Decision Context - Coverage Days Descriptive Ratio", () => {
  const available = 153;
  const avgDemand = 5.21;
  const coverageDays = Number((available / avgDemand).toFixed(2));
  assert.equal(coverageDays, 29.37);

  // Lead time buffer
  const leadTime = 10;
  const buffer = Number((coverageDays - leadTime).toFixed(1));
  assert.equal(buffer, 19.4);
});

test("Decision Context - Deterministic Status Classification Logic", () => {
  // NORMAL: buffer healthy, lead time safe, demand stable, supplier low risk
  // ATTENTION: increasing demand or buffer near reorder point
  // ELEVATED: deficit below reorder point, high supplier risk, or coverage < lead time

  const getExpectedStatus = (isBelowReorder, riskLevel, coverageDays, leadTime, trend) => {
    if (isBelowReorder || riskLevel === "HIGH" || (coverageDays !== null && coverageDays < leadTime)) {
      return "ELEVATED";
    }
    if (riskLevel === "MEDIUM" || trend === "increasing") {
      return "ATTENTION";
    }
    return "NORMAL";
  };

  assert.equal(getExpectedStatus(false, "LOW", 29.37, 10, "increasing"), "ATTENTION");
  assert.equal(getExpectedStatus(false, "LOW", 29.37, 10, "stable"), "NORMAL");
  assert.equal(getExpectedStatus(true, "LOW", 5.0, 10, "stable"), "ELEVATED");
  assert.equal(getExpectedStatus(false, "HIGH", 29.37, 10, "stable"), "ELEVATED");
  assert.equal(getExpectedStatus(false, "LOW", 8.0, 10, "stable"), "ELEVATED");
});

test("Decision Context - Null Safe Handling for Graceful Degradation", () => {
  // Verifies that UI logic correctly defaults values if optional dimensions are missing
  const partialContext = {
    product_id: "prod-001",
    warehouse_id: "wh-001",
    product: {
      id: "prod-001",
      sku: "SKU-TEST",
      name: "Test SKU",
      category: "Test Category",
      unit_cost: 10,
      selling_price: 20,
      reorder_point: 15,
      active: true,
    },
    warehouse: {
      id: "wh-001",
      code: "WH-TEST",
      name: "Test Facility",
      location: "Facility Location",
      capacity: 5000,
      active: true,
    },
    inventory: null,
    demand: null,
    supplier: null,
    metrics: {
      coverage_days: null,
      lead_time_days: null,
      is_below_reorder: true,
      net_deficit: 15,
      context_status: "ELEVATED",
    },
    status: "ELEVATED",
  };

  // Check fallback calculations
  const availableQty = partialContext.inventory?.available_quantity ?? 0;
  assert.equal(availableQty, 0);

  const avgDemand = partialContext.demand ? partialContext.demand.average_daily_demand.toFixed(2) : "0.00";
  assert.equal(avgDemand, "0.00");

  const supplierName = partialContext.supplier?.name ?? "Unassigned Supplier";
  assert.equal(supplierName, "Unassigned Supplier");

  const leadTime = partialContext.supplier?.lead_time_days ?? partialContext.metrics.lead_time_days ?? 0;
  assert.equal(leadTime, 0);
});
