from __future__ import annotations

import random
from typing import Any

from app.data.dataset import ScenarioMetadata, ScenarioType
from app.domain.inventory import Inventory
from app.domain.product import Product
from app.domain.supplier import Supplier
from app.domain.warehouse import Warehouse


def apply_scenario(
    scenario_type: ScenarioType,
    products: list[Product],
    suppliers: list[Supplier],
    warehouses: list[Warehouse],
    inventory: list[Inventory],
    rnd: random.Random,
    target_product_ids: list[str] | None = None,
    target_supplier_ids: list[str] | None = None,
    custom_params: dict[str, Any] | None = None,
) -> tuple[
    list[Product],
    list[Supplier],
    list[Warehouse],
    list[Inventory],
    ScenarioMetadata,
]:
    """Applies a controlled operational scenario to generated ShopFlow data.

    This function strictly modifies underlying data attributes (such as lead times,
    reliability scores, or inventory quantities) to simulate operational conditions.
    It does NOT implement detection rules, forecasting, or recommendation algorithms.
    """
    params = custom_params.copy() if custom_params else {}
    target_skus: list[str] = []
    affected_supplier_codes: list[str] = []

    # Map lookups
    prod_map = {p.id: p for p in products}
    sup_map = {s.id: s for s in suppliers}

    # Resolve target products (default to first 1 or 2 products if not explicitly provided)
    if target_product_ids is None:
        selected_prod_ids = [products[0].id] if products else []
    else:
        selected_prod_ids = [pid for pid in target_product_ids if pid in prod_map]

    # Resolve target suppliers (default to first supplier if not explicitly provided)
    if target_supplier_ids is None:
        selected_sup_ids = [suppliers[0].id] if suppliers else []
    else:
        selected_sup_ids = [sid for sid in target_supplier_ids if sid in sup_map]

    target_skus = [prod_map[pid].sku for pid in selected_prod_ids if pid in prod_map]
    affected_supplier_codes = [sup_map[sid].code for sid in selected_sup_ids if sid in sup_map]

    updated_products = list(products)
    updated_suppliers = list(suppliers)
    updated_warehouses = list(warehouses)
    updated_inventory: list[Inventory] = []

    if scenario_type == ScenarioType.NORMAL:
        description = "Nominal ShopFlow operating state: balanced inventory levels and dependable supplier lead times."
        # No abnormal mutations needed; nominal generation baseline
        updated_inventory = list(inventory)

    elif scenario_type == ScenarioType.LOW_INVENTORY:
        description = (
            f"Depleted inventory state: target SKUs ({', '.join(target_skus)}) "
            "have physical on-hand quantities below their replenishment reorder points."
        )
        for inv in inventory:
            if inv.product_id in selected_prod_ids:
                reorder = inv.reorder_point
                # Set on-hand well below reorder point (e.g. 25% - 60% of reorder)
                ratio = rnd.uniform(0.25, 0.60)
                new_on_hand = max(1, int(reorder * ratio))
                # Reserved must be strictly <= on-hand
                new_reserved = min(inv.quantity_reserved, int(new_on_hand * 0.3))
                updated_inv = inv.model_copy(
                    update={
                        "quantity_on_hand": new_on_hand,
                        "quantity_reserved": new_reserved,
                    }
                )
                updated_inventory.append(updated_inv)
            else:
                updated_inventory.append(inv)

    elif scenario_type == ScenarioType.APPROACHING_REORDER:
        description = (
            f"Buffer boundary state: target SKUs ({', '.join(target_skus)}) "
            "are hovering immediately above their reorder points."
        )
        for inv in inventory:
            if inv.product_id in selected_prod_ids:
                reorder = inv.reorder_point
                # Just above reorder point (1.02 to 1.12 x reorder)
                margin = rnd.uniform(1.02, 1.12)
                new_on_hand = max(reorder + 1, int(reorder * margin))
                new_reserved = min(inv.quantity_reserved, int(new_on_hand * 0.15))
                updated_inv = inv.model_copy(
                    update={
                        "quantity_on_hand": new_on_hand,
                        "quantity_reserved": new_reserved,
                    }
                )
                updated_inventory.append(updated_inv)
            else:
                updated_inventory.append(inv)

    elif scenario_type == ScenarioType.SUPPLIER_DELAY:
        delay_days = params.get("delay_days", 45)
        description = (
            f"Supply shock: target suppliers ({', '.join(affected_supplier_codes)}) "
            f"experience substantial fulfillment lead time extensions (+{delay_days} days)."
        )
        new_suppliers = []
        for s in updated_suppliers:
            if s.id in selected_sup_ids:
                extended_lead = s.lead_time_days + delay_days
                new_suppliers.append(s.model_copy(update={"lead_time_days": extended_lead}))
            else:
                new_suppliers.append(s)
        updated_suppliers = new_suppliers
        updated_inventory = list(inventory)

    elif scenario_type == ScenarioType.SUPPLIER_UNRELIABLE:
        degraded_reliability = params.get("target_reliability", 0.55)
        description = (
            f"Vendor volatility: target suppliers ({', '.join(affected_supplier_codes)}) "
            f"exhibit degraded fulfillment reliability ({degraded_reliability:.2f})."
        )
        new_suppliers = []
        for s in updated_suppliers:
            if s.id in selected_sup_ids:
                new_suppliers.append(s.model_copy(update={"reliability": degraded_reliability}))
            else:
                new_suppliers.append(s)
        updated_suppliers = new_suppliers
        updated_inventory = list(inventory)

    elif scenario_type == ScenarioType.POTENTIAL_STOCKOUT:
        description = (
            f"Acute stockout state: target SKUs ({', '.join(target_skus)}) "
            "have near-zero unallocated inventory with high committed orders."
        )
        for inv in inventory:
            if inv.product_id in selected_prod_ids:
                # Critical on-hand, with reserved matching or within 1 unit of on-hand
                low_on_hand = rnd.randint(3, 8)
                reserved = max(0, low_on_hand - rnd.choice([0, 1]))
                updated_inv = inv.model_copy(
                    update={
                        "quantity_on_hand": low_on_hand,
                        "quantity_reserved": reserved,
                    }
                )
                updated_inventory.append(updated_inv)
            else:
                updated_inventory.append(inv)
    else:
        raise ValueError(f"Unsupported scenario type: '{scenario_type}'")

    metadata = ScenarioMetadata(
        scenario_type=scenario_type,
        description=description,
        target_skus=target_skus,
        target_suppliers=affected_supplier_codes,
        parameters=params,
    )

    return (
        updated_products,
        updated_suppliers,
        updated_warehouses,
        updated_inventory,
        metadata,
    )
