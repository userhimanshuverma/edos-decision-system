from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.demand import DemandRecord
from app.domain.inventory import Inventory
from app.domain.product import Product
from app.domain.supplier import Supplier
from app.domain.warehouse import Warehouse



class ScenarioType(str, Enum):
    """Operational scenario types representing controlled synthetic ShopFlow conditions."""

    NORMAL = "normal"
    LOW_INVENTORY = "low_inventory"
    APPROACHING_REORDER = "approaching_reorder"
    SUPPLIER_DELAY = "supplier_delay"
    SUPPLIER_UNRELIABLE = "supplier_unreliable"
    POTENTIAL_STOCKOUT = "potential_stockout"


class ScenarioMetadata(BaseModel):
    """Metadata describing a synthetic data operational scenario."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    scenario_type: ScenarioType = Field(..., description="Classification of the operational scenario")
    description: str = Field(..., min_length=1, description="Human-readable scenario description")
    target_skus: list[str] = Field(default_factory=list, description="SKUs specifically affected by the scenario")
    target_suppliers: list[str] = Field(default_factory=list, description="Supplier codes affected by the scenario")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Arbitrary scenario parameters")


class ShopFlowDataset(BaseModel):
    """Container holding a complete, consistent ShopFlow synthetic dataset."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    seed: int = Field(..., description="Random seed used to generate this dataset")
    scenario: ScenarioMetadata | None = Field(default=None, description="Operational scenario metadata if configured")
    products: list[Product] = Field(default_factory=list, description="List of generated products")
    suppliers: list[Supplier] = Field(default_factory=list, description="List of generated suppliers")
    warehouses: list[Warehouse] = Field(default_factory=list, description="List of generated warehouses")
    inventory: list[Inventory] = Field(default_factory=list, description="List of generated inventory positions")
    demand: list[DemandRecord] = Field(default_factory=list, description="List of generated historical demand records")

    def validate_integrity(self) -> None:
        """Validates that all inventory and demand records reference existing products and warehouses."""
        product_ids = {p.id for p in self.products}
        warehouse_ids = {w.id for w in self.warehouses}

        for inv in self.inventory:
            if inv.product_id not in product_ids:
                raise ValueError(
                    f"Inventory position '{inv.id}' references unknown product_id '{inv.product_id}'"
                )
            if inv.warehouse_id not in warehouse_ids:
                raise ValueError(
                    f"Inventory position '{inv.id}' references unknown warehouse_id '{inv.warehouse_id}'"
                )
            if inv.quantity_reserved > inv.quantity_on_hand:
                raise ValueError(
                    f"Inventory position '{inv.id}' has quantity_reserved ({inv.quantity_reserved}) > quantity_on_hand ({inv.quantity_on_hand})"
                )

        for dem in self.demand:
            if dem.product_id not in product_ids:
                raise ValueError(
                    f"Demand record '{dem.id}' references unknown product_id '{dem.product_id}'"
                )
            if dem.warehouse_id not in warehouse_ids:
                raise ValueError(
                    f"Demand record '{dem.id}' references unknown warehouse_id '{dem.warehouse_id}'"
                )
            if dem.quantity < 0:
                raise ValueError(
                    f"Demand record '{dem.id}' has negative quantity ({dem.quantity})"
                )

    def get_product(self, product_id: str) -> Product | None:
        """Finds product by id."""
        for p in self.products:
            if p.id == product_id:
                return p
        return None

    def get_supplier(self, supplier_id: str) -> Supplier | None:
        """Finds supplier by id."""
        for s in self.suppliers:
            if s.id == supplier_id:
                return s
        return None

    def get_warehouse(self, warehouse_id: str) -> Warehouse | None:
        """Finds warehouse by id."""
        for w in self.warehouses:
            if w.id == warehouse_id:
                return w
        return None

    def get_inventory(self, product_id: str, warehouse_id: str) -> Inventory | None:
        """Finds inventory record for a specific product and warehouse."""
        for inv in self.inventory:
            if inv.product_id == product_id and inv.warehouse_id == warehouse_id:
                return inv
        return None

    def get_demand(self, demand_id: str) -> DemandRecord | None:
        """Finds demand record by id."""
        for dem in self.demand:
            if dem.id == demand_id:
                return dem
        return None

    def get_demand_by_product(self, product_id: str) -> list[DemandRecord]:
        """Finds demand records for a specific product."""
        return [dem for dem in self.demand if dem.product_id == product_id]

    def get_demand_by_warehouse(self, warehouse_id: str) -> list[DemandRecord]:
        """Finds demand records for a specific warehouse."""
        return [dem for dem in self.demand if dem.warehouse_id == warehouse_id]

    def get_demand_by_product_and_warehouse(self, product_id: str, warehouse_id: str) -> list[DemandRecord]:
        """Finds demand records for a specific product and warehouse."""
        return [dem for dem in self.demand if dem.product_id == product_id and dem.warehouse_id == warehouse_id]


    def to_dict(self) -> dict[str, Any]:
        """Serializes the dataset to a JSON-compatible dictionary."""
        return self.model_dump(mode="json")

    def to_json(self, indent: int = 2) -> str:
        """Serializes the dataset to a formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_file(self, file_path: str | Path, indent: int = 2) -> Path:
        """Saves the serialized dataset to a JSON file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(indent=indent), encoding="utf-8")
        return path

    @classmethod
    def from_json(cls, json_str: str) -> ShopFlowDataset:
        """Deserializes a dataset from a JSON string and validates integrity."""
        dataset = cls.model_validate_json(json_str)
        dataset.validate_integrity()
        return dataset

    @classmethod
    def from_file(cls, file_path: str | Path) -> ShopFlowDataset:
        """Reads and deserializes a dataset from a JSON file."""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        return cls.from_json(content)
