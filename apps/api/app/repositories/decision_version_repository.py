from __future__ import annotations

from typing import Sequence

from app.domain.context import DecisionContext
from app.domain.decision import Decision
from app.domain.decision_version import DecisionSnapshot, DecisionVersion


class DuplicateDecisionVersionError(ValueError):
    """Raised when attempting to store a version with an identifier or version number that already exists."""


class ConflictingVersionNumberError(DuplicateDecisionVersionError):
    """Raised when attempting to store a version with a version number that conflicts with an existing version for the same decision."""


class DecisionVersionRepository:
    """In-memory data access layer for historical decision versions.

    Provides deterministic storage, version numbering, ordering, and duplicate protection
    for decision snapshots.
    
    Guarantees:
    - Positive, monotonic version numbering per decision (starting at 1).
    - Deterministic ordering sorted strictly by version_number ascending.
    - Deep defensive copies on write and read to prevent internal state mutation.
    - Decision isolation: queries for a decision return only versions for that decision.
    - In-memory single-process scope (non-persistent across restarts, no distributed locking).
    """

    def __init__(self, versions: Sequence[DecisionVersion] | None = None) -> None:
        """Initializes the repository with an empty store or preloaded versions."""
        self._versions: dict[str, DecisionVersion] = {}
        self._counter: int = 0

        if versions:
            for version in versions:
                self.record(version)

    def generate_id(self) -> str:
        """Generates the next unique, human-readable version identifier (VER-XXXX)."""
        while True:
            self._counter += 1
            candidate = f"VER-{self._counter:04d}"
            if candidate not in self._versions:
                return candidate

    def get_next_version_number(self, decision_id: str) -> int:
        """Computes the next positive version number for a given decision.
        
        Returns 1 if no versions exist for this decision; otherwise returns max + 1.
        """
        norm_decision_id = decision_id.strip()
        matching = [
            v.version_number
            for v in self._versions.values()
            if v.decision_id == norm_decision_id
        ]
        if not matching:
            return 1
        return max(matching) + 1

    def record(self, version: DecisionVersion) -> DecisionVersion:
        """Stores a validated DecisionVersion in memory.

        Raises:
            DuplicateDecisionVersionError: If a version with this unique ID already exists.
            ConflictingVersionNumberError: If a version with the same version_number already exists for this decision.

        Returns a defensive deep copy of the stored version.
        """
        if version.id in self._versions:
            raise DuplicateDecisionVersionError(
                f"Decision version with identifier '{version.id}' already exists"
            )

        norm_decision_id = version.decision_id.strip()
        for existing in self._versions.values():
            if (
                existing.decision_id == norm_decision_id
                and existing.version_number == version.version_number
            ):
                raise ConflictingVersionNumberError(
                    f"Version number {version.version_number} already exists for decision '{version.decision_id}'"
                )

        stored_copy = version.model_copy(deep=True)
        self._versions[version.id] = stored_copy
        return stored_copy.model_copy(deep=True)

    def create_version(
        self,
        decision: Decision,
        *,
        version_id: str | None = None,
        description: str | None = None,
        context: DecisionContext | None = None,
    ) -> DecisionVersion:
        """Constructs and stores a new version snapshot for an existing decision."""
        vid = version_id if version_id is not None else self.generate_id()
        vnum = self.get_next_version_number(decision.id)
        snapshot = DecisionSnapshot.from_decision(decision, context=context)

        version = DecisionVersion(
            id=vid,
            decision_id=decision.id,
            version_number=vnum,
            snapshot=snapshot,
            description=description.strip() if description is not None and description.strip() else None,
        )
        return self.record(version)

    def get_by_id(self, version_id: str) -> DecisionVersion | None:
        """Retrieves a single version by its unique identifier, or None if not found."""
        norm_id = version_id.strip()
        record = self._versions.get(norm_id)
        if record is None:
            return None
        return record.model_copy(deep=True)

    def get_by_version_number(
        self,
        decision_id: str,
        version_number: int,
    ) -> DecisionVersion | None:
        """Retrieves a specific version for a decision by its version number, or None if not found."""
        norm_decision_id = decision_id.strip()
        for v in self._versions.values():
            if v.decision_id == norm_decision_id and v.version_number == version_number:
                return v.model_copy(deep=True)
        return None

    def get_by_decision_id(self, decision_id: str) -> list[DecisionVersion]:
        """Retrieves all versions associated with a decision in deterministic version_number order.

        Sorted strictly by version_number ascending.
        Returns an empty list if the decision has no recorded versions.
        """
        norm_decision_id = decision_id.strip()
        matching = [
            v for v in self._versions.values()
            if v.decision_id == norm_decision_id
        ]
        sorted_records = sorted(matching, key=lambda v: v.version_number)
        return [v.model_copy(deep=True) for v in sorted_records]

    def list_by_decision_id(self, decision_id: str) -> list[DecisionVersion]:
        """Alias for get_by_decision_id."""
        return self.get_by_decision_id(decision_id)

    def list_all(self, decision_id: str | None = None) -> list[DecisionVersion]:
        """Lists versions held by the repository in deterministic order.

        Optionally filtered by decision_id.
        Sorted primarily by decision_id ascending, and secondarily by version_number ascending.
        """
        if decision_id is not None:
            return self.get_by_decision_id(decision_id)

        all_records = list(self._versions.values())
        sorted_records = sorted(all_records, key=lambda v: (v.decision_id, v.version_number))
        return [v.model_copy(deep=True) for v in sorted_records]

    def remove(self, version_id: str) -> bool:
        """Removes a version by ID (used for rollback on failed operations)."""
        norm_id = version_id.strip()
        if norm_id in self._versions:
            del self._versions[norm_id]
            return True
        return False

    def clear(self) -> None:
        """Clears all stored versions and resets sequence counter."""
        self._versions.clear()
        self._counter = 0

    def __len__(self) -> int:
        """Returns total number of versions currently stored."""
        return len(self._versions)

    def __bool__(self) -> bool:
        """Repository instance is always truthy regardless of version count."""
        return True
