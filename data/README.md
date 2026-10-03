# Data Directory

This directory stores datasets, schemas, model artifacts, and test data used by the EDOS Decision System.

## Structure

```text
data/
├── raw/            # Raw, unprocessed datasets
├── processed/      # Cleaned and processed datasets & scenario fixtures
│   ├── scenario_low_inventory.json
│   └── scenario_potential_stockout.json
└── schemas/        # Schema definitions and sample fixtures
    ├── shopflow_dataset_schema.json
    └── shopflow_sample_dataset.json
```

## ShopFlow Synthetic Data Engine (Day 5)

The Synthetic Data Engine generates realistic, deterministic, and internally consistent operational datasets using the Day 4 Pydantic domain models (`Product`, `Supplier`, `Warehouse`, `Inventory`).

### Deterministic Generation & Seeds

All randomness is strictly isolated within an instance-specific `random.Random(seed)`. No global random state is mutated.

- Given the same seed and parameters, `generate_shopflow_dataset(seed=X)` produces the exact same serialized dataset.
- Different seeds generate distinct, reproducible operational worlds.
- Inventory timestamps are derived deterministically from a fixed base UTC reference date (`2026-10-01T12:00:00Z`).
- Referential integrity is strictly validated: every inventory position maps to existing products and warehouses, with `quantity_reserved <= quantity_on_hand`.

### Available Controlled Scenarios

The engine provides controlled operational scenarios that manipulate underlying data parameters for subsequent testing phases:

| Scenario | Identifier | Operational Data Condition |
|---|---|---|
| **Normal** | `normal` | Nominal inventory buffer (2x–4x reorder point), standard supplier lead times (5–14 days), high reliability (>=0.90). |
| **Low Inventory** | `low_inventory` | Target SKUs have physical on-hand quantity below their reorder threshold (`quantity_on_hand < reorder_point`). |
| **Approaching Reorder** | `approaching_reorder` | Target SKUs hover immediately above reorder point (`reorder_point <= quantity_on_hand <= 1.15 * reorder_point`). |
| **Supplier Delay** | `supplier_delay` | Target suppliers experience extended fulfillment lead times (+45 days). |
| **Supplier Unreliable** | `supplier_unreliable` | Target suppliers exhibit degraded fulfillment reliability (0.45–0.65). |
| **Potential Stockout** | `potential_stockout` | Severe depletion: minimal on-hand quantity with nearly all units reserved (`available_quantity <= 2`). |

*Note: Scenarios strictly shape underlying data parameters without implementing detection logic or recommendation algorithms (reserved for Day 6+).*

### Running the Generator & Generating Fixtures

From `apps/api`:

```bash
# Generate default baseline dataset (printed to stdout)
python -m app.data.generator --seed 42

# Generate a controlled scenario and write to file
python -m app.data.generator --seed 42 --scenario potential_stockout --output ../../data/processed/scenario_potential_stockout.json

# Run the test suite
pytest tests/test_synthetic_data.py
```

