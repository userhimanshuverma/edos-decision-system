from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from app.data.dataset import ShopFlowDataset
from app.data.generator import generate_shopflow_dataset
from app.domain.decision import Decision, DecisionStatus


class DuplicateDecisionError(ValueError):
    """Raised when attempting to store a decision with an identifier that already exists."""


class DecisionRepository:
    """In-memory data access layer for operational business decisions.

    Provides deterministic storage, retrieval, and listing of decisions
    with unique identifier generation and duplicate protection.
    """

    def __init__(
        self,
        decisions: Sequence[Decision] | None = None,
        dataset: ShopFlowDataset | None = None,
    ) -> None:
        """Initializes the repository with optional preloaded decisions and dataset."""
        if dataset is None:
            self._dataset = generate_shopflow_dataset(seed=42)
        else:
            self._dataset = dataset

        self._decisions: dict[str, Decision] = {}
        self._counter: int = 0

        if decisions:
            for decision in decisions:
                self.create(decision=decision)

    @property
    def dataset(self) -> ShopFlowDataset:
        """Returns the underlying ShopFlow dataset container for reference integrity checks."""
        return self._dataset

    def generate_id(self) -> str:
        """Generates the next unique, human-readable decision identifier (DEC-XXXX)."""
        while True:
            self._counter += 1
            candidate = f"DEC-{self._counter:04d}"
            if candidate not in self._decisions:
                return candidate

    def create(
        self,
        target: Decision | str | None = None,
        warehouse_id: str | None = None,
        *,
        product_id: str | None = None,
        decision: Decision | None = None,
        id: str | None = None,
        created_at: datetime | None = None,
        status: DecisionStatus | None = None,
    ) -> Decision:
        """Creates and stores a decision entity in memory.

        Supports invocation with either:
        - A pre-constructed Decision instance (`repo.create(decision)`)
        - Positional arguments (`repo.create("prod-001", "wh-001")`)
        - Keyword arguments (`repo.create(product_id="prod-001", warehouse_id="wh-001")`)
        """
        # Determine whether a Decision instance was passed
        resolved_decision: Decision
        if isinstance(target, Decision):
            resolved_decision = target
        elif decision is not None:
            resolved_decision = decision
        else:
            # Resolve product_id and warehouse_id from parameters
            resolved_prod_id = target if isinstance(target, str) else product_id
            if resolved_prod_id is None:
                raise ValueError("product_id is required to create a decision")
            if warehouse_id is None:
                raise ValueError("warehouse_id is required to create a decision")

            decision_id = id if id is not None else self.generate_id()
            resolved_decision = Decision(
                id=decision_id,
                product_id=resolved_prod_id,
                warehouse_id=warehouse_id,
                created_at=created_at if created_at is not None else datetime.now(timezone.utc),
                status=status if status is not None else DecisionStatus.DRAFT,
            )

        if resolved_decision.id in self._decisions:
            raise DuplicateDecisionError(
                f"Decision with identifier '{resolved_decision.id}' already exists"
            )

        # Store a defensive deep copy
        stored_copy = resolved_decision.model_copy(deep=True)
        self._decisions[resolved_decision.id] = stored_copy
        return stored_copy.model_copy(deep=True)

    def save(self, decision: Decision) -> Decision:
        """Alias for create with an existing Decision instance."""
        return self.create(decision=decision)

    def add(self, decision: Decision) -> Decision:
        """Alias for create with an existing Decision instance."""
        return self.create(decision=decision)

    def get_by_id(self, decision_id: str) -> Decision | None:
        """Retrieves a decision by its unique identifier, returning None if not found."""
        norm_id = decision_id.strip()
        record = self._decisions.get(norm_id)
        if record is None:
            return None
        return record.model_copy(deep=True)

    def list_all(
        self,
        product_id: str | None = None,
        warehouse_id: str | None = None,
    ) -> list[Decision]:
        """Lists decisions held by the repository with deterministic ordering.

        Preserves deterministic ordering sorted by creation timestamp followed by ID.
        """
        records = list(self._decisions.values())

        if product_id is not None:
            norm_prod = product_id.strip()
            records = [d for d in records if d.product_id == norm_prod]

        if warehouse_id is not None:
            norm_wh = warehouse_id.strip()
            records = [d for d in records if d.warehouse_id == norm_wh]

        # Deterministic ordering by (created_at, id)
        sorted_records = sorted(records, key=lambda d: (d.created_at, d.id))
        return [d.model_copy(deep=True) for d in sorted_records]

    def product_exists(self, product_id: str) -> bool:
        """Verifies if the referenced product exists in the catalog."""
        return self._dataset.get_product(product_id.strip()) is not None

    def warehouse_exists(self, warehouse_id: str) -> bool:
        """Verifies if the referenced warehouse exists in the facility directory."""
        return self._dataset.get_warehouse(warehouse_id.strip()) is not None

    def clear(self) -> None:
        """Clears all stored decisions and resets ID sequence counter."""
        self._decisions.clear()
        self._counter = 0
