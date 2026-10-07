from enum import Enum
from app.data.dataset import ShopFlowDataset
from app.data.generator import generate_shopflow_dataset
from app.domain.supplier import Supplier, SupplierRiskLevel, classify_supplier_risk


class SupplierRepository:
    """In-memory data access layer for ShopFlow supplier entities.

    Provides reliable, deterministic read access to the current ShopFlow
    supplier catalog backed by the ShopFlow synthetic data engine.
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

    def list_all(self, active_only: bool = False) -> list[Supplier]:
        """Retrieves all supplier records with deterministic ordering by supplier ID.

        Args:
            active_only: If True, only returns suppliers where active is True.
        """
        records = self._dataset.suppliers
        if active_only:
            records = [s for s in records if s.active]
        # Guarantee deterministic sorting by ID
        return sorted(records, key=lambda s: s.id)

    def get_by_id(self, supplier_id: str) -> Supplier | None:
        """Retrieves a single supplier by its unique supplier ID (e.g., 'sup-001')."""
        norm_id = supplier_id.strip()
        for supplier in self._dataset.suppliers:
            if supplier.id == norm_id:
                return supplier
        return None

    def get_by_code(self, code: str) -> Supplier | None:
        """Retrieves a single supplier by its unique business code (case-insensitive, e.g., 'SUP-PAC-01')."""
        norm_code = code.strip().upper()
        for supplier in self._dataset.suppliers:
            if supplier.code.upper() == norm_code:
                return supplier
        return None

    def get_active_suppliers(self) -> list[Supplier]:
        """Retrieves all active suppliers ordered deterministically by supplier ID."""
        return self.list_all(active_only=True)

    def supplier_exists(self, supplier_id: str) -> bool:
        """Checks if a supplier ID exists in the underlying dataset."""
        return self.get_by_id(supplier_id) is not None

    def code_exists(self, code: str) -> bool:
        """Checks if a supplier code exists in the underlying dataset."""
        return self.get_by_code(code) is not None

    def get_supplier_risk(self, supplier: Supplier) -> SupplierRiskLevel:
        """Evaluates the deterministic operational risk level of a supplier."""
        return classify_supplier_risk(
            lead_time_days=supplier.lead_time_days,
            reliability=supplier.reliability,
            active=supplier.active,
        )

    def get_supplier_for_product(
        self,
        product_id: str,
        category: str | None = None,
    ) -> Supplier | None:
        """Deterministically resolves the primary operational supplier for a product.

        Uses category affinity mapping when available. If the supplier code
        is not present in the dataset or category is unspecified, falls back to a
        stable modulo assignment based on product ID across available suppliers.
        """
        if not self._dataset.suppliers:
            return None

        # 1. Check category affinity mapping if category provided
        if category and category in CATEGORY_SUPPLIER_MAP:
            target_code = CATEGORY_SUPPLIER_MAP[category]
            found = self.get_by_code(target_code)
            if found is not None:
                return found

        # 2. Deterministic fallback: modulo across deterministically sorted suppliers
        sorted_suppliers = self.list_all()
        if not sorted_suppliers:
            return None

        digits = "".join(ch for ch in product_id if ch.isdigit())
        if digits:
            idx = (int(digits) - 1) % len(sorted_suppliers)
        else:
            idx = sum(ord(c) for c in product_id) % len(sorted_suppliers)

        return sorted_suppliers[idx]


# Deterministic category to primary supplier code blueprint mapping
CATEGORY_SUPPLIER_MAP: dict[str, str] = {
    "Industrial Electronics": "SUP-PAC-01",
    "Mechanical & Motion": "SUP-APX-02",
    "Power Distribution": "SUP-VNG-03",
    "Sensors & Instrumentation": "SUP-OMN-04",
    "Industrial Networking": "SUP-PAC-01",
    "Hydraulics & Pneumatics": "SUP-APX-02",
    "Safety Systems": "SUP-VNG-03",
}
