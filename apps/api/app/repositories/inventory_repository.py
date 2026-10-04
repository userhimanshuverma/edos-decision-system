from __future__ import annotations

from app.data.dataset import ShopFlowDataset
from app.data.generator import generate_shopflow_dataset
from app.domain.inventory import Inventory


class InventoryRepository:
    """In-memory data access layer for ShopFlow inventory records.

    Provides reliable, deterministic read access to the current ShopFlow
    inventory state backed by the ShopFlow synthetic data engine.
    """

    def __init__(self, dataset: ShopFlowDataset | None = None) -> None:
        """Initializes the repository with a dataset or defaults to canonical seed 42."""
        if dataset is None:
            self._dataset = generate_shopflow_dataset(seed=42)
        else:
            self._dataset = dataset

    @property
    def dataset(self) -> ShopFlowDataset:
        """Returns the underlying ShopFlow dataset container."""
        return self._dataset

    def list_all(
        self,
        product_id: str | None = None,
        warehouse_id: str | None = None,
    ) -> list[Inventory]:
        """Retrieves all inventory records, optionally filtered by product or warehouse."""
        records = self._dataset.inventory
        if product_id is not None:
            records = [inv for inv in records if inv.product_id == product_id]
        if warehouse_id is not None:
            records = [inv for inv in records if inv.warehouse_id == warehouse_id]
        return list(records)

    def get_by_id(self, inventory_id: str) -> Inventory | None:
        """Retrieves a single inventory record by its inventory ID."""
        for inv in self._dataset.inventory:
            if inv.id == inventory_id:
                return inv
        return None

    def get_by_product_id(self, product_id: str) -> list[Inventory]:
        """Retrieves all inventory positions belonging to a specific product."""
        return [inv for inv in self._dataset.inventory if inv.product_id == product_id]

    def get_by_warehouse_id(self, warehouse_id: str) -> list[Inventory]:
        """Retrieves all inventory positions belonging to a specific warehouse."""
        return [inv for inv in self._dataset.inventory if inv.warehouse_id == warehouse_id]

    def product_exists(self, product_id: str) -> bool:
        """Checks if a product exists in the underlying catalog."""
        return self._dataset.get_product(product_id) is not None

    def warehouse_exists(self, warehouse_id: str) -> bool:
        """Checks if a warehouse exists in the underlying dataset."""
        return self._dataset.get_warehouse(warehouse_id) is not None
