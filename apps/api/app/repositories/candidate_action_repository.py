from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from app.domain.candidate_action import (
    ActionParameters,
    ActionType,
    CandidateAction,
)


class DuplicateCandidateActionError(ValueError):
    """Raised when attempting to store a candidate action with an identifier that already exists."""


class CandidateActionRepository:
    """In-memory data access layer for candidate operational actions.

    Provides deterministic storage, retrieval, ordering, and duplicate protection
    for candidate actions associated with business decisions.

    Guarantees:
    - Stable, predictable sequential action identifier generation (ACT-XXXX).
    - Deep defensive copies on write and read paths to prevent mutable state leakage.
    - Decision isolation: queries filtered by decision return strictly that decision's actions.
    - Deterministic ordering: sorted primarily by created_at ascending, secondarily by action id ascending.
    - In-memory single-process scope (non-persistent across restarts, no distributed locking).
    """

    def __init__(self, actions: Sequence[CandidateAction] | None = None) -> None:
        """Initializes the repository with an empty store or preloaded candidate actions."""
        self._actions: dict[str, CandidateAction] = {}
        self._counter: int = 0

        if actions:
            for action in actions:
                self.record(action)

    def generate_id(self) -> str:
        """Generates the next unique, human-readable action identifier (ACT-XXXX)."""
        while True:
            self._counter += 1
            candidate = f"ACT-{self._counter:04d}"
            if candidate not in self._actions:
                return candidate

    def record(self, action: CandidateAction) -> CandidateAction:
        """Stores a validated CandidateAction in memory.

        Raises:
            DuplicateCandidateActionError: If an action with this unique ID already exists.

        Returns a defensive deep copy of the stored action.
        """
        norm_id = action.id.strip()
        if norm_id in self._actions:
            raise DuplicateCandidateActionError(
                f"Candidate action with identifier '{action.id}' already exists"
            )

        stored_copy = action.model_copy(deep=True)
        self._actions[stored_copy.id] = stored_copy
        return stored_copy.model_copy(deep=True)

    def create_action(
        self,
        decision_id: str,
        action_type: ActionType | str,
        parameters: ActionParameters | dict[str, Any],
        *,
        id: str | None = None,
        created_at: datetime | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CandidateAction:
        """Constructs and stores a new candidate action."""
        act_id = id if id is not None else self.generate_id()
        resolved_type = (
            action_type
            if isinstance(action_type, ActionType)
            else ActionType(action_type)
        )
        action = CandidateAction(
            id=act_id,
            decision_id=decision_id.strip(),
            action_type=resolved_type,
            parameters=parameters,
            created_at=created_at if created_at is not None else datetime.now(timezone.utc),
            description=description,
            metadata=metadata if metadata is not None else {},
        )
        return self.record(action)

    def get_by_id(self, action_id: str) -> CandidateAction | None:
        """Retrieves a single candidate action by its unique identifier, or None if not found."""
        norm_id = action_id.strip()
        record = self._actions.get(norm_id)
        if record is None:
            return None
        return record.model_copy(deep=True)

    def list_by_decision_id(self, decision_id: str) -> list[CandidateAction]:
        """Retrieves all candidate actions belonging to a specific decision.

        Returns actions sorted deterministically by (created_at, id) ascending.
        Returns an empty list if no actions exist for this decision.
        """
        return self.list_all(decision_id=decision_id)

    def list_all(self, decision_id: str | None = None) -> list[CandidateAction]:
        """Lists candidate actions held by the repository in deterministic order.

        Optionally filtered by decision_id.
        Sorted primarily by created_at ascending, and secondarily by action id ascending.
        """
        records = list(self._actions.values())
        if decision_id is not None:
            norm_decision_id = decision_id.strip()
            records = [a for a in records if a.decision_id == norm_decision_id]

        sorted_records = sorted(records, key=lambda a: (a.created_at, a.id))
        return [a.model_copy(deep=True) for a in sorted_records]

    def remove(self, action_id: str) -> bool:
        """Removes an action by ID (used for rollback on failed operations)."""
        norm_id = action_id.strip()
        if norm_id in self._actions:
            del self._actions[norm_id]
            return True
        return False

    def clear(self) -> None:
        """Clears all stored candidate actions and resets the sequence counter."""
        self._actions.clear()
        self._counter = 0

    def __len__(self) -> int:
        """Returns total number of candidate actions currently stored."""
        return len(self._actions)

    def __bool__(self) -> bool:
        """Repository instance is always truthy."""
        return True
