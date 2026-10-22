from __future__ import annotations

from typing import Sequence
from app.domain.replay import DecisionReplayRecord


class DuplicateReplayRecordError(ValueError):
    """Raised when attempting to store a replay record with an ID that already exists."""


class ReplayRepository:
    """In-memory repository for Decision Replay records.

    Provides deterministic storage, retrieval, ordering, and isolation
    for forensic decision replay executions.

    Guarantees:
    - Stable sequential identifier generation (RPL-XXXX).
    - Unique execution identifier generation (REX-XXXX).
    - Deep defensive copies on write and read paths.
    - Decision and version isolation: queries return strictly scoped records.
    - Deterministic ordering: sorted primarily by created_at descending, secondarily by id descending.
    - In-memory architecture with zero external database dependencies.
    """

    def __init__(self, records: Sequence[DecisionReplayRecord] | None = None) -> None:
        """Initializes the repository with an empty store or preloaded records."""
        self._records: dict[str, DecisionReplayRecord] = {}
        self._id_counter: int = 0
        self._exec_counter: int = 0

        if records:
            for rec in records:
                self.record(rec)

    def generate_id(self) -> str:
        """Generates the next unique replay record identifier (RPL-XXXX)."""
        while True:
            self._id_counter += 1
            candidate = f"RPL-{self._id_counter:04d}"
            if candidate not in self._records:
                return candidate

    def generate_execution_id(self) -> str:
        """Generates the next unique replay execution identifier (REX-XXXX)."""
        self._exec_counter += 1
        return f"REX-{self._exec_counter:04d}"

    def record(self, record: DecisionReplayRecord) -> DecisionReplayRecord:
        """Stores a validated DecisionReplayRecord in memory.

        Raises:
            DuplicateReplayRecordError: If a replay record with this ID already exists.

        Returns a defensive deep copy of the stored record.
        """
        norm_id = record.id.strip()
        if norm_id in self._records:
            raise DuplicateReplayRecordError(
                f"Replay record with identifier '{record.id}' already exists"
            )

        defensive_copy = record.model_copy(deep=True)
        self._records[norm_id] = defensive_copy
        return defensive_copy.model_copy(deep=True)

    def get_by_id(self, record_id: str) -> DecisionReplayRecord | None:
        """Retrieves a replay record by unique identifier. Returns defensive copy or None."""
        norm_id = record_id.strip()
        rec = self._records.get(norm_id)
        if rec is None:
            return None
        return rec.model_copy(deep=True)

    def get_latest_for_decision(
        self,
        decision_id: str,
        version_id: str | None = None,
    ) -> DecisionReplayRecord | None:
        """Retrieves the most recent replay record for a decision (and optional version)."""
        matching = self.list_by_decision_id(decision_id=decision_id, version_id=version_id)
        if not matching:
            return None
        return matching[0].model_copy(deep=True)

    def list_by_decision_id(
        self,
        decision_id: str,
        version_id: str | None = None,
    ) -> list[DecisionReplayRecord]:
        """Returns all replay records for a decision, sorted newest first (created_at desc, id desc)."""
        norm_decision_id = decision_id.strip()
        norm_version_id = version_id.strip() if version_id is not None else None

        matching: list[DecisionReplayRecord] = []
        for rec in self._records.values():
            if rec.decision_id != norm_decision_id:
                continue
            if norm_version_id is not None and rec.version_id != norm_version_id:
                continue
            matching.append(rec)

        matching.sort(key=lambda r: (r.created_at, r.id), reverse=True)
        return [r.model_copy(deep=True) for r in matching]

    def list_all(self, decision_id: str | None = None) -> list[DecisionReplayRecord]:
        """Returns all stored replay records or records filtered by decision_id."""
        if decision_id is not None:
            return self.list_by_decision_id(decision_id)
        all_recs = list(self._records.values())
        all_recs.sort(key=lambda r: (r.created_at, r.id), reverse=True)
        return [r.model_copy(deep=True) for r in all_recs]

    def remove(self, record_id: str) -> bool:
        """Removes a stored replay record by ID. Returns True if removed, False otherwise."""
        norm_id = record_id.strip()
        return self._records.pop(norm_id, None) is not None

    def clear(self) -> None:
        """Clears all stored replay records and resets identifier counters."""
        self._records.clear()
        self._id_counter = 0
        self._exec_counter = 0

    def __len__(self) -> int:
        return len(self._records)
