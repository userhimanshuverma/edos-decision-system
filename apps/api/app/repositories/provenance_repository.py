from __future__ import annotations

from typing import Sequence
from app.domain.provenance import DecisionProvenanceTrace


class DuplicateProvenanceTraceError(ValueError):
    """Raised when attempting to store a provenance trace with an ID that already exists."""


class ProvenanceRepository:
    """In-memory data access layer for Decision Provenance Traces.

    Provides deterministic storage, retrieval, integrity validation, and duplicate protection
    for end-to-end decision provenance traces.

    Guarantees:
    - Stable, predictable identifier generation: PRV-XXXX, EXEC-XXXX, INP-XXXX, RUL-XXXX, CLC-XXXX, RES-XXXX.
    - Deep defensive copies on write and read to eliminate mutable state leakage.
    - Preserves decision isolation: traces are indexed strictly per decision.
    - Multi-execution disambiguation: multiple executions for the same decision are preserved chronologically.
    - Deterministic ordering: sorted by (created_at desc, id desc).
    - In-memory single-process scope (non-persistent across restarts).
    """

    def __init__(self, traces: Sequence[DecisionProvenanceTrace] | None = None) -> None:
        self._traces: dict[str, DecisionProvenanceTrace] = {}
        self._by_decision_id: dict[str, list[str]] = {}
        self._counter: int = 0
        self._exec_counter: int = 0
        self._inp_counter: int = 0
        self._rul_counter: int = 0
        self._clc_counter: int = 0
        self._res_counter: int = 0

        if traces:
            for trace in traces:
                self.record(trace)

    def generate_id(self) -> str:
        """Generates the next unique, human-readable trace identifier (PRV-XXXX)."""
        while True:
            self._counter += 1
            candidate = f"PRV-{self._counter:04d}"
            if candidate not in self._traces:
                return candidate

    def generate_execution_id(self) -> str:
        """Generates the next unique execution identifier (EXEC-XXXX)."""
        self._exec_counter += 1
        return f"EXEC-{self._exec_counter:04d}"

    def generate_input_id(self) -> str:
        """Generates the next unique input step identifier (INP-XXXX)."""
        self._inp_counter += 1
        return f"INP-{self._inp_counter:04d}"

    def generate_rule_id(self) -> str:
        """Generates the next unique rule step identifier (RUL-XXXX)."""
        self._rul_counter += 1
        return f"RUL-{self._rul_counter:04d}"

    def generate_calculation_id(self) -> str:
        """Generates the next unique calculation step identifier (CLC-XXXX)."""
        self._clc_counter += 1
        return f"CLC-{self._clc_counter:04d}"

    def generate_result_id(self) -> str:
        """Generates the next unique result step identifier (RES-XXXX)."""
        self._res_counter += 1
        return f"RES-{self._res_counter:04d}"

    def record(self, trace: DecisionProvenanceTrace) -> DecisionProvenanceTrace:
        """Stores a validated DecisionProvenanceTrace in memory.

        Raises:
            DuplicateProvenanceTraceError: If a trace with this unique ID already exists.

        Returns a defensive deep copy of the stored trace.
        """
        norm_id = trace.id.strip()
        if norm_id in self._traces:
            raise DuplicateProvenanceTraceError(
                f"Provenance trace with identifier '{trace.id}' already exists"
            )

        stored_copy = trace.model_copy(deep=True)
        self._traces[stored_copy.id] = stored_copy

        norm_decision_id = stored_copy.decision_id.strip()
        if norm_decision_id not in self._by_decision_id:
            self._by_decision_id[norm_decision_id] = []
        self._by_decision_id[norm_decision_id].append(stored_copy.id)

        return stored_copy.model_copy(deep=True)

    def get_by_id(self, trace_id: str) -> DecisionProvenanceTrace | None:
        """Retrieves a single provenance trace by its unique identifier, or None if not found."""
        norm_id = trace_id.strip()
        trace = self._traces.get(norm_id)
        if trace is None:
            return None
        return trace.model_copy(deep=True)

    def get_latest_for_decision(
        self,
        decision_id: str,
        version_id: str | None = None,
    ) -> DecisionProvenanceTrace | None:
        """Retrieves the most recent provenance trace for a decision.

        Optionally filtered by exact decision version.
        """
        traces = self.list_for_decision(decision_id, version_id=version_id)
        if not traces:
            return None
        return traces[0].model_copy(deep=True)

    def list_for_decision(
        self,
        decision_id: str,
        version_id: str | None = None,
    ) -> list[DecisionProvenanceTrace]:
        """Lists all provenance traces for a decision, deterministically ordered (created_at desc, id desc).

        Optionally filtered by exact decision version.
        """
        norm_decision_id = decision_id.strip()
        trace_ids = self._by_decision_id.get(norm_decision_id, [])
        traces = [self._traces[t_id] for t_id in trace_ids if t_id in self._traces]

        if version_id is not None:
            norm_ver_id = version_id.strip()
            traces = [t for t in traces if t.version_id == norm_ver_id]

        sorted_traces = sorted(
            traces,
            key=lambda t: (t.created_at, t.id),
            reverse=True,
        )
        return [t.model_copy(deep=True) for t in sorted_traces]

    def remove(self, trace_id: str) -> bool:
        """Removes a trace by ID (used for rollback on failed operations)."""
        norm_id = trace_id.strip()
        if norm_id in self._traces:
            trace = self._traces.pop(norm_id)
            decision_traces = self._by_decision_id.get(trace.decision_id, [])
            if norm_id in decision_traces:
                decision_traces.remove(norm_id)
            return True
        return False

    def clear(self) -> None:
        """Clears all stored traces and resets sequence counters."""
        self._traces.clear()
        self._by_decision_id.clear()
        self._counter = 0
        self._exec_counter = 0
        self._inp_counter = 0
        self._rul_counter = 0
        self._clc_counter = 0
        self._res_counter = 0

    def __len__(self) -> int:
        return len(self._traces)

    def __bool__(self) -> bool:
        return True
