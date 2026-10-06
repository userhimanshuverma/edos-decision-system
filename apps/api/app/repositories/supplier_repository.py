from __future__ import annotations

from enum import Enum
from app.data.dataset import ShopFlowDataset
from app.data.generator import generate_shopflow_dataset
from app.domain.supplier import Supplier


class SupplierRiskLevel(str, Enum):
    """Deterministic supplier operational risk classification.

    Classification is based purely on the supplier's own observable operational profile:
    - LOW: Dependable supplier with standard fulfillment speed (reliability >= 0.92, lead_time <= 14 days, active)
    - MEDIUM: Moderate operational lead time or reliability (lead_time 15–21 days, or reliability 0.85–0.92)
    - HIGH: Elevated operational risk (reliability < 0.85, lead_time > 21 days, or inactive)
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


def classify_supplier_risk(
    lead_time_days: int,
    reliability: float,
    active: bool = True,
) -> SupplierRiskLevel:
    """Deterministically classifies supplier operational risk based on lead time and reliability.

    Rules:
    1. Inactive suppliers represent high operational risk if called upon.
    2. Reliability < 0.85 or lead_time > 21 days indicates high operational risk.
    3. Reliability < 0.92 or lead_time > 14 days indicates medium (elevated) operational risk.
    4. Reliability >= 0.92 and lead_time <= 14 days indicates low operational risk.
    """
    if not active:
        return SupplierRiskLevel.HIGH
    if reliability < 0.85 or lead_time_days > 21:
        return SupplierRiskLevel.HIGH
    if reliability < 0.92 or lead_time_days > 14:
        return SupplierRiskLevel.MEDIUM
    return SupplierRiskLevel.LOW


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
