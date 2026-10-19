from __future__ import annotations

from typing import Sequence
from app.domain.validation import DecisionValidationReport


class DuplicateValidationReportError(ValueError):
    """Raised when attempting to store a validation report with an identifier that already exists."""


class ValidationRepository:
    """In-memory repository for business decision validation reports.

    Provides deterministic storage, retrieval, ordering, and duplicate protection
    for candidate action hard-constraint validation reports.

    Guarantees:
    - Stable sequential identifier generation (VAL-XXXX).
    - Deep defensive copies on write and read paths.
    - Decision isolation: queries filtered by decision return strictly that decision's validation reports.
    - Deterministic ordering: sorted primarily by created_at ascending, secondarily by validation report id ascending.
    """

    def __init__(self, reports: Sequence[DecisionValidationReport] | None = None) -> None:
        """Initializes the repository with an empty store or preloaded validation reports."""
        self._reports: dict[str, DecisionValidationReport] = {}
        self._counter: int = 0

        if reports:
            for rep in reports:
                self.record(rep)

    def generate_id(self) -> str:
        """Generates the next unique validation report identifier (VAL-XXXX)."""
        while True:
            self._counter += 1
            candidate = f"VAL-{self._counter:04d}"
            if candidate not in self._reports:
                return candidate

    def record(self, report: DecisionValidationReport) -> DecisionValidationReport:
        """Stores a validated DecisionValidationReport in memory.

        Raises:
            DuplicateValidationReportError: If a report with this ID already exists.

        Returns a defensive deep copy of the stored validation report.
        """
        norm_id = report.id.strip()
        if norm_id in self._reports:
            raise DuplicateValidationReportError(
                f"Validation report with identifier '{report.id}' already exists"
            )

        defensive_copy = report.model_copy(deep=True)
        self._reports[norm_id] = defensive_copy
        return defensive_copy.model_copy(deep=True)

    def get_by_id(self, validation_id: str) -> DecisionValidationReport | None:
        """Retrieves a validation report by unique identifier. Returns defensive copy or None."""
        norm_id = validation_id.strip()
        rep = self._reports.get(norm_id)
        if rep is None:
            return None
        return rep.model_copy(deep=True)

    def get_latest_for_decision(self, decision_id: str) -> DecisionValidationReport | None:
        """Retrieves the latest validation report generated for a specific business decision."""
        reports = self.list_by_decision_id(decision_id)
        if not reports:
            return None
        return reports[-1].model_copy(deep=True)

    def list_by_decision_id(self, decision_id: str) -> list[DecisionValidationReport]:
        """Returns all validation reports for a decision, sorted deterministically by (created_at, id)."""
        norm_decision_id = decision_id.strip()
        matching = [
            rep for rep in self._reports.values()
            if rep.decision_id == norm_decision_id
        ]
        matching.sort(key=lambda r: (r.created_at, r.id))
        return [r.model_copy(deep=True) for r in matching]

    def list_all(self, decision_id: str | None = None) -> list[DecisionValidationReport]:
        """Returns all stored validation reports or validation reports filtered by decision_id."""
        if decision_id is not None:
            return self.list_by_decision_id(decision_id)
        all_reports = list(self._reports.values())
        all_reports.sort(key=lambda r: (r.created_at, r.id))
        return [r.model_copy(deep=True) for r in all_reports]

    def remove(self, validation_id: str) -> bool:
        """Removes a stored validation report by ID. Returns True if removed, False otherwise."""
        norm_id = validation_id.strip()
        return self._reports.pop(norm_id, None) is not None

    def clear(self) -> None:
        """Clears all stored validation reports and resets sequential ID counter."""
        self._reports.clear()
        self._counter = 0

    def __len__(self) -> int:
        return len(self._reports)
