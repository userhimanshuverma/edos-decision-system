from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random

from app.data.dataset import ScenarioMetadata, ScenarioType, ShopFlowDataset
from app.data.scenarios import apply_scenario
from app.domain.inventory import Inventory
from app.domain.product import Product
from app.domain.supplier import Supplier
from app.domain.warehouse import Warehouse

# Base deterministic timestamp for all generated synthetic timestamps
DEFAULT_BASE_DATETIME = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)

# Realistic product catalog blueprints
PRODUCT_BLUEPRINTS = [
    {
        "sku": "SKU-ELEC-1001",
        "name": "Industrial IoT Gateway Edge-X",
        "category": "Industrial Electronics",
        "unit_cost": 125.0,
        "selling_price": 210.0,
        "reorder_point": 50,
    },
    {
        "sku": "SKU-ELEC-1002",
        "name": "Quad-Core Embedded Logic Controller",
        "category": "Industrial Electronics",
        "unit_cost": 310.0,
        "selling_price": 495.0,
        "reorder_point": 35,
    },
    {
        "sku": "SKU-MECH-2001",
        "name": "High-Torque Brushless Servo Motor",
        "category": "Mechanical & Motion",
        "unit_cost": 88.0,
        "selling_price": 149.0,
        "reorder_point": 70,
    },
    {
        "sku": "SKU-MECH-2002",
        "name": "Precision Ground Ball Screw Assembly",
        "category": "Mechanical & Motion",
        "unit_cost": 65.0,
        "selling_price": 115.0,
        "reorder_point": 60,
    },
    {
        "sku": "SKU-POWR-3001",
        "name": "24V 20A Industrial DIN-Rail PSU",
        "category": "Power Distribution",
        "unit_cost": 45.0,
        "selling_price": 85.0,
        "reorder_point": 90,
    },
    {
        "sku": "SKU-POWR-3002",
        "name": "Modular LiFePO4 48V Storage Cell",
        "category": "Power Distribution",
        "unit_cost": 230.0,
        "selling_price": 380.0,
        "reorder_point": 30,
    },
    {
        "sku": "SKU-NETW-4001",
        "name": "Managed 8-Port Gigabit Switch",
        "category": "Industrial Networking",
        "unit_cost": 160.0,
        "selling_price": 275.0,
        "reorder_point": 45,
    },
    {
        "sku": "SKU-NETW-4002",
        "name": "Ruggedized Dual-SIM LTE Router",
        "category": "Industrial Networking",
        "unit_cost": 140.0,
        "selling_price": 240.0,
        "reorder_point": 40,
    },
    {
        "sku": "SKU-SENS-5001",
        "name": "Infrared Thermal Line Scanner",
        "category": "Sensors & Instrumentation",
        "unit_cost": 290.0,
        "selling_price": 475.0,
        "reorder_point": 25,
    },
    {
        "sku": "SKU-SENS-5002",
        "name": "Triaxial Piezoelectric Vibration Sensor",
        "category": "Sensors & Instrumentation",
        "unit_cost": 92.0,
        "selling_price": 160.0,
        "reorder_point": 80,
    },
    {
        "sku": "SKU-HYDR-6001",
        "name": "Proportional Hydraulic Servo Valve",
        "category": "Hydraulics & Pneumatics",
        "unit_cost": 175.0,
        "selling_price": 295.0,
        "reorder_point": 30,
    },
    {
        "sku": "SKU-SAFE-7001",
        "name": "SIL-3 Rated E-Stop Safety Relay",
        "category": "Safety Systems",
        "unit_cost": 38.0,
        "selling_price": 72.0,
        "reorder_point": 110,
    },
]

# Realistic supplier blueprints
SUPPLIER_BLUEPRINTS = [
    {
        "code": "SUP-PAC-01",
        "name": "Pacific Dynamics Core",
        "lead_time_days": 10,
        "reliability": 0.98,
    },
    {
        "code": "SUP-APX-02",
        "name": "Apex Motion & Machine Corp",
        "lead_time_days": 14,
        "reliability": 0.95,
    },
    {
        "code": "SUP-VNG-03",
        "name": "Vanguard Industrial Power",
        "lead_time_days": 7,
        "reliability": 0.97,
    },
    {
        "code": "SUP-OMN-04",
        "name": "OmniSensor Systems Global",
        "lead_time_days": 12,
        "reliability": 0.93,
    },
    {
        "code": "SUP-GLB-05",
        "name": "Global Automation Components",
        "lead_time_days": 20,
        "reliability": 0.91,
    },
    {
        "code": "SUP-KST-06",
        "name": "Kestrel Machining Works",
        "lead_time_days": 15,
        "reliability": 0.94,
    },
]

# Realistic warehouse blueprints
WAREHOUSE_BLUEPRINTS = [
    {
        "code": "WH-EAST-01",
        "name": "Eastern Logistics Hub",
        "location": "Allentown, PA",
        "capacity": 150000,
    },
    {
        "code": "WH-CENT-02",
        "name": "Midwest Distribution Center",
        "location": "Indianapolis, IN",
        "capacity": 275000,
    },
    {
        "code": "WH-WEST-03",
        "name": "Pacific Gateway Depot",
        "location": "Stockton, CA",
        "capacity": 180000,
    },
    {
        "code": "WH-STH-04",
        "name": "Southern Cross Terminal",
        "location": "Dallas, TX",
        "capacity": 140000,
    },
]


def generate_shopflow_dataset(
    seed: int = 42,
    product_count: int = 10,
    supplier_count: int = 4,
    warehouse_count: int = 3,
    scenario: ScenarioType | str = ScenarioType.NORMAL,
    base_date: datetime | None = None,
    target_product_ids: list[str] | None = None,
    target_supplier_ids: list[str] | None = None,
) -> ShopFlowDataset:
    """Generates a complete, deterministic, and internally consistent ShopFlow dataset.

    All random state is isolated within a local random.Random(seed) generator.
    Given the identical configuration and seed, this function produces identical data.
    """
    if isinstance(scenario, str):
        scenario = ScenarioType(scenario)

    rnd = random.Random(seed)
    ref_time = base_date or DEFAULT_BASE_DATETIME

    # 1. Generate Products
    products: list[Product] = []
    actual_product_count = max(1, product_count)

    for i in range(actual_product_count):
        prod_id = f"prod-{i + 1:03d}"
        if i < len(PRODUCT_BLUEPRINTS):
            bp = PRODUCT_BLUEPRINTS[i]
            sku = bp["sku"]
            name = bp["name"]
            category = bp["category"]
            # Apply deterministic subtle variance around blueprint cost & price
            cost_factor = 1.0 + (rnd.uniform(-0.05, 0.05))
            unit_cost = round(bp["unit_cost"] * cost_factor, 2)
            margin = rnd.uniform(0.40, 0.65)
            selling_price = round(unit_cost * (1.0 + margin), 2)
            reorder_point = bp["reorder_point"]
        else:
            sku = f"SKU-GEN-{i + 1:04d}"
            name = f"ShopFlow Component #{i + 1}"
            category = rnd.choice(["Industrial Electronics", "Mechanical & Motion", "Power Distribution"])
            unit_cost = round(rnd.uniform(25.0, 300.0), 2)
            margin = rnd.uniform(0.35, 0.60)
            selling_price = round(unit_cost * (1.0 + margin), 2)
            reorder_point = rnd.choice([25, 50, 75, 100])

        products.append(
            Product(
                id=prod_id,
                sku=sku,
                name=name,
                category=category,
                unit_cost=unit_cost,
                selling_price=selling_price,
                reorder_point=reorder_point,
                active=True,
            )
        )

    # 2. Generate Suppliers
    suppliers: list[Supplier] = []
    actual_supplier_count = max(1, supplier_count)

    for i in range(actual_supplier_count):
        sup_id = f"sup-{i + 1:03d}"
        if i < len(SUPPLIER_BLUEPRINTS):
            sbp = SUPPLIER_BLUEPRINTS[i]
            code = sbp["code"]
            name = sbp["name"]
            lead_time = sbp["lead_time_days"]
            reliability = sbp["reliability"]
        else:
            code = f"SUP-GEN-{i + 1:02d}"
            name = f"General Industrial Supplier #{i + 1}"
            lead_time = rnd.randint(7, 21)
            reliability = round(rnd.uniform(0.90, 0.99), 2)

        suppliers.append(
            Supplier(
                id=sup_id,
                code=code,
                name=name,
                lead_time_days=lead_time,
                reliability=reliability,
                active=True,
            )
        )

    # 3. Generate Warehouses
    warehouses: list[Warehouse] = []
    actual_warehouse_count = max(1, warehouse_count)

    for i in range(actual_warehouse_count):
        wh_id = f"wh-{i + 1:03d}"
        if i < len(WAREHOUSE_BLUEPRINTS):
            wbp = WAREHOUSE_BLUEPRINTS[i]
            code = wbp["code"]
            name = wbp["name"]
            location = wbp["location"]
            capacity = wbp["capacity"]
        else:
            code = f"WH-GEN-{i + 1:02d}"
            name = f"Regional Facility #{i + 1}"
            location = rnd.choice(["Chicago, IL", "Atlanta, GA", "Phoenix, AZ", "Seattle, WA"])
            capacity = rnd.randint(100000, 300000)

        warehouses.append(
            Warehouse(
                id=wh_id,
                code=code,
                name=name,
                location=location,
                capacity=capacity,
                active=True,
            )
        )

    # 4. Generate Inventory (Product x Warehouse Matrix)
    inventory: list[Inventory] = []
    inv_seq = 1

    for prod in products:
        for wh in warehouses:
            inv_id = f"inv-{prod.id}-{wh.id}"
            reorder = prod.reorder_point

            # Nominal baseline inventory: healthy buffer (2x to 4x reorder point)
            buffer_multiplier = rnd.uniform(2.0, 4.0)
            on_hand = int(reorder * buffer_multiplier)
            reserved_pct = rnd.uniform(0.05, 0.20)
            reserved = int(on_hand * reserved_pct)

            # Ensure valid bounds
            on_hand = max(0, on_hand)
            reserved = max(0, min(reserved, on_hand))

            # Deterministic timestamp offset (0 to 1440 minutes)
            offset_minutes = rnd.randint(0, 1440)
            inv_timestamp = ref_time + timedelta(minutes=offset_minutes)

            inventory.append(
                Inventory(
                    id=inv_id,
                    product_id=prod.id,
                    warehouse_id=wh.id,
                    quantity_on_hand=on_hand,
                    quantity_reserved=reserved,
                    reorder_point=reorder,
                    updated_at=inv_timestamp,
                )
            )
            inv_seq += 1

    # 5. Apply Controlled Scenario Adjustments
    products, suppliers, warehouses, inventory, scenario_meta = apply_scenario(
        scenario_type=scenario,
        products=products,
        suppliers=suppliers,
        warehouses=warehouses,
        inventory=inventory,
        rnd=rnd,
        target_product_ids=target_product_ids,
        target_supplier_ids=target_supplier_ids,
    )

    dataset = ShopFlowDataset(
        seed=seed,
        scenario=scenario_meta,
        products=products,
        suppliers=suppliers,
        warehouses=warehouses,
        inventory=inventory,
    )

    # Validate referential integrity and bounds
    dataset.validate_integrity()

    return dataset


def generate_scenario_dataset(
    scenario: ScenarioType | str,
    seed: int = 42,
    **kwargs,
) -> ShopFlowDataset:
    """Convenience helper to generate a dataset for a specific operational scenario."""
    return generate_shopflow_dataset(seed=seed, scenario=scenario, **kwargs)


def _cli() -> None:
    """Command-line interface to produce deterministic ShopFlow fixture files."""
    parser = argparse.ArgumentParser(description="ShopFlow Synthetic Data Generator (Day 5)")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic generator seed (default: 42)")
    parser.add_argument("--products", type=int, default=10, help="Number of products (default: 10)")
    parser.add_argument("--suppliers", type=int, default=4, help="Number of suppliers (default: 4)")
    parser.add_argument("--warehouses", type=int, default=3, help="Number of warehouses (default: 3)")
    parser.add_argument(
        "--scenario",
        type=str,
        default="normal",
        choices=[s.value for s in ScenarioType],
        help="Operational scenario name (default: normal)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (e.g. data/schemas/shopflow_sample_dataset.json)",
    )

    args = parser.parse_args()

    dataset = generate_shopflow_dataset(
        seed=args.seed,
        product_count=args.products,
        supplier_count=args.suppliers,
        warehouse_count=args.warehouses,
        scenario=ScenarioType(args.scenario),
    )

    if args.output:
        out_path = Path(args.output)
        dataset.save_to_file(out_path)
        print(f"Generated ShopFlow dataset saved to: {out_path} ({len(dataset.products)} products, {len(dataset.inventory)} inventory positions)")
    else:
        print(dataset.to_json(indent=2))


if __name__ == "__main__":
    _cli()
