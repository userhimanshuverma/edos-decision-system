from __future__ import annotations

from typing import Sequence
from app.domain.evidence import (
    DecisionAssumption,
    DecisionEvidence,
    DecisionEvidenceSheet,
    EvidenceCategory,
    EvidenceType,
)


class EvidenceRepositoryError(ValueError):
    """Base error for evidence repository exceptions."""


class DuplicateEvidenceError(EvidenceRepositoryError):
    """Raised when attempting to store an evidence item with an identifier that already exists."""


class DuplicateAssumptionError(EvidenceRepositoryError):
    """Raised when attempting to store an assumption with an identifier that already exists."""


class DuplicateEvidenceSheetError(EvidenceRepositoryError):
    """Raised when attempting to store an evidence sheet with an identifier that already exists."""


class EvidenceRepository:
    """In-memory repository for business decision evidence and assumptions.

    Provides deterministic storage, retrieval, filtering, ordering, and duplicate protection
    for decision evidence items, explicit assumptions, and consolidated evidence sheets.

    Guarantees:
    - Stable sequential identifier generation (EVD-XXXX, ASM-XXXX, EVS-XXXX).
    - Deep defensive copies on write and read paths.
    - Decision boundary enforcement: items queried for a decision return strictly that decision's records.
    - Deterministic ordering: sorted primarily by created_at ascending, secondarily by identifier ascending.
    """

    def __init__(
        self,
        evidence_items: Sequence[DecisionEvidence] | None = None,
        assumptions: Sequence[DecisionAssumption] | None = None,
        sheets: Sequence[DecisionEvidenceSheet] | None = None,
    ) -> None:
        self._evidence: dict[str, DecisionEvidence] = {}
        self._assumptions: dict[str, DecisionAssumption] = {}
        self._sheets: dict[str, DecisionEvidenceSheet] = {}
        self._evd_counter: int = 0
        self._asm_counter: int = 0
        self._evs_counter: int = 0

        if evidence_items:
            for ev in evidence_items:
                self.record_evidence(ev)

        if assumptions:
            for asm in assumptions:
                self.record_assumption(asm)

        if sheets:
            for sheet in sheets:
                self.record_sheet(sheet)

    def generate_evidence_id(self) -> str:
        """Generates the next unique evidence identifier (EVD-XXXX)."""
        while True:
            self._evd_counter += 1
            candidate = f"EVD-{self._evd_counter:04d}"
            if candidate not in self._evidence:
                return candidate

    def generate_assumption_id(self) -> str:
        """Generates the next unique assumption identifier (ASM-XXXX)."""
        while True:
            self._asm_counter += 1
            candidate = f"ASM-{self._asm_counter:04d}"
            if candidate not in self._assumptions:
                return candidate

    def generate_sheet_id(self) -> str:
        """Generates the next unique evidence sheet identifier (EVS-XXXX)."""
        while True:
            self._evs_counter += 1
            candidate = f"EVS-{self._evs_counter:04d}"
            if candidate not in self._sheets:
                return candidate

    def record_evidence(self, evidence: DecisionEvidence) -> DecisionEvidence:
        """Stores a DecisionEvidence item in memory.

        Raises:
            DuplicateEvidenceError: If an evidence item with this ID already exists.

        Returns a defensive deep copy of the stored evidence item.
        """
        norm_id = evidence.id.strip()
        if norm_id in self._evidence:
            raise DuplicateEvidenceError(f"Evidence item with identifier '{evidence.id}' already exists")

        defensive_copy = evidence.model_copy(deep=True)
        self._evidence[norm_id] = defensive_copy
        return defensive_copy.model_copy(deep=True)

    def record_assumption(self, assumption: DecisionAssumption) -> DecisionAssumption:
        """Stores a DecisionAssumption in memory.

        Raises:
            DuplicateAssumptionError: If an assumption with this ID already exists.

        Returns a defensive deep copy of the stored assumption.
        """
        norm_id = assumption.id.strip()
        if norm_id in self._assumptions:
            raise DuplicateAssumptionError(f"Assumption with identifier '{assumption.id}' already exists")

        defensive_copy = assumption.model_copy(deep=True)
        self._assumptions[norm_id] = defensive_copy
        return defensive_copy.model_copy(deep=True)

    def record_sheet(self, sheet: DecisionEvidenceSheet) -> DecisionEvidenceSheet:
        """Stores a DecisionEvidenceSheet in memory.

        Raises:
            DuplicateEvidenceSheetError: If an evidence sheet with this ID already exists.

        Returns a defensive deep copy of the stored evidence sheet.
        """
        norm_id = sheet.id.strip()
        if norm_id in self._sheets:
            raise DuplicateEvidenceSheetError(f"Evidence sheet with identifier '{sheet.id}' already exists")

        defensive_copy = sheet.model_copy(deep=True)
        self._sheets[norm_id] = defensive_copy
        return defensive_copy.model_copy(deep=True)

    def get_evidence_by_id(self, evidence_id: str) -> DecisionEvidence | None:
        """Retrieves an evidence item by ID. Returns defensive copy or None."""
        norm_id = evidence_id.strip()
        item = self._evidence.get(norm_id)
        if item is None:
            return None
        return item.model_copy(deep=True)

    def get_assumption_by_id(self, assumption_id: str) -> DecisionAssumption | None:
        """Retrieves an assumption item by ID. Returns defensive copy or None."""
        norm_id = assumption_id.strip()
        item = self._assumptions.get(norm_id)
        if item is None:
            return None
        return item.model_copy(deep=True)

    def get_sheet_by_id(self, sheet_id: str) -> DecisionEvidenceSheet | None:
        """Retrieves an evidence sheet by ID. Returns defensive copy or None."""
        norm_id = sheet_id.strip()
        sheet = self._sheets.get(norm_id)
        if sheet is None:
            return None
        return sheet.model_copy(deep=True)

    def get_latest_sheet_for_decision(self, decision_id: str) -> DecisionEvidenceSheet | None:
        """Retrieves the most recently compiled evidence sheet for a specific business decision."""
        sheets = self.list_sheets_by_decision(decision_id)
        if not sheets:
            return None
        return sheets[-1].model_copy(deep=True)

    def list_evidence_by_decision(
        self,
        decision_id: str,
        evidence_type: EvidenceType | None = None,
        category: EvidenceCategory | None = None,
        action_id: str | None = None,
        version_id: str | None = None,
    ) -> list[DecisionEvidence]:
        """Returns all evidence items for a decision matching optional filters, deterministically sorted."""
        norm_decision_id = decision_id.strip()
        matching = [
            item for item in self._evidence.values()
            if item.decision_id == norm_decision_id
            and (evidence_type is None or item.evidence_type == evidence_type)
            and (category is None or item.category == category)
            and (action_id is None or item.action_id == action_id.strip())
            and (version_id is None or item.version_id == version_id.strip())
        ]
        matching.sort(key=lambda ev: (ev.created_at, ev.id))
        return [ev.model_copy(deep=True) for ev in matching]

    def list_assumptions_by_decision(
        self,
        decision_id: str,
        category: EvidenceCategory | None = None,
        action_id: str | None = None,
        version_id: str | None = None,
    ) -> list[DecisionAssumption]:
        """Returns all explicit assumptions for a decision matching optional filters, deterministically sorted."""
        norm_decision_id = decision_id.strip()
        matching = [
            item for item in self._assumptions.values()
            if item.decision_id == norm_decision_id
            and (category is None or item.category == category)
            and (action_id is None or item.action_id == action_id.strip())
            and (version_id is None or item.version_id == version_id.strip())
        ]
        matching.sort(key=lambda asm: (asm.created_at, asm.id))
        return [asm.model_copy(deep=True) for asm in matching]

    def list_sheets_by_decision(self, decision_id: str) -> list[DecisionEvidenceSheet]:
        """Returns all evidence sheets for a decision, deterministically sorted."""
        norm_decision_id = decision_id.strip()
        matching = [
            sheet for sheet in self._sheets.values()
            if sheet.decision_id == norm_decision_id
        ]
        matching.sort(key=lambda s: (s.created_at, s.id))
        return [s.model_copy(deep=True) for s in matching]

    def remove_evidence(self, evidence_id: str) -> bool:
        """Removes a stored evidence item by ID. Returns True if removed, False otherwise."""
        norm_id = evidence_id.strip()
        return self._evidence.pop(norm_id, None) is not None

    def remove_assumption(self, assumption_id: str) -> bool:
        """Removes a stored assumption item by ID. Returns True if removed, False otherwise."""
        norm_id = assumption_id.strip()
        return self._assumptions.pop(norm_id, None) is not None

    def remove_sheet(self, sheet_id: str) -> bool:
        """Removes a stored evidence sheet by ID. Returns True if removed, False otherwise."""
        norm_id = sheet_id.strip()
        return self._sheets.pop(norm_id, None) is not None

    def clear(self) -> None:
        """Clears all stored evidence, assumptions, sheets, and resets ID counters."""
        self._evidence.clear()
        self._assumptions.clear()
        self._sheets.clear()
        self._evd_counter = 0
        self._asm_counter = 0
        self._evs_counter = 0

    def __len__(self) -> int:
        return len(self._evidence)
