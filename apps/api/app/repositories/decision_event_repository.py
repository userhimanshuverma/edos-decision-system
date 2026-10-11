from __future__ import annotations

from typing import Sequence

from app.domain.decision_event import DecisionEvent


class DuplicateDecisionEventError(ValueError):
    """Raised when attempting to store an event with an identifier that already exists."""


DuplicateEventError = DuplicateDecisionEventError


class DecisionEventRepository:
    """In-memory data access layer for decision audit history events.

    Provides deterministic storage, chronological retrieval, and duplicate protection
    for decision lifecycle events.
    """

    def __init__(self, events: Sequence[DecisionEvent] | None = None) -> None:
        """Initializes the repository with an empty store or preloaded events."""
        self._events: dict[str, DecisionEvent] = {}
        self._counter: int = 0

        if events:
            for event in events:
                self.record(event)

    def generate_id(self) -> str:
        """Generates the next unique, human-readable event identifier (EVT-XXXX)."""
        while True:
            self._counter += 1
            candidate = f"EVT-{self._counter:04d}"
            if candidate not in self._events:
                return candidate

    def record(self, event: DecisionEvent) -> DecisionEvent:
        """Stores a validated DecisionEvent in memory.

        Raises DuplicateDecisionEventError if an event with this ID already exists.
        Returns a defensive deep copy of the stored event.
        """
        if event.id in self._events:
            raise DuplicateDecisionEventError(
                f"Decision event with identifier '{event.id}' already exists"
            )

        stored_copy = event.model_copy(deep=True)
        self._events[event.id] = stored_copy
        return stored_copy.model_copy(deep=True)

    def append(self, event: DecisionEvent) -> DecisionEvent:
        """Alias for record."""
        return self.record(event)

    def get_by_id(self, event_id: str) -> DecisionEvent | None:
        """Retrieves a single event by its unique identifier, or None if not found."""
        norm_id = event_id.strip()
        record = self._events.get(norm_id)
        if record is None:
            return None
        return record.model_copy(deep=True)

    def get_by_decision_id(self, decision_id: str) -> list[DecisionEvent]:
        """Retrieves all events associated with a decision in deterministic chronological order.

        Order is sorted primarily by `occurred_at` ascending, and secondarily by `id` ascending.
        Returns an empty list if the decision has no recorded events.
        """
        norm_id = decision_id.strip()
        matching = [e for e in self._events.values() if e.decision_id == norm_id]
        sorted_records = sorted(matching, key=lambda e: (e.occurred_at, e.id))
        return [e.model_copy(deep=True) for e in sorted_records]

    def list_by_decision_id(self, decision_id: str) -> list[DecisionEvent]:
        """Alias for get_by_decision_id."""
        return self.get_by_decision_id(decision_id)

    def list_all(self, decision_id: str | None = None) -> list[DecisionEvent]:
        """Lists events held by the repository in deterministic chronological order.

        Optionally filtered by decision_id.
        """
        if decision_id is not None:
            return self.get_by_decision_id(decision_id)

        all_records = list(self._events.values())
        sorted_records = sorted(all_records, key=lambda e: (e.occurred_at, e.id))
        return [e.model_copy(deep=True) for e in sorted_records]

    def remove(self, event_id: str) -> bool:
        """Removes an event by ID (used for rollback on failed atomic operations)."""
        norm_id = event_id.strip()
        if norm_id in self._events:
            del self._events[norm_id]
            return True
        return False

    def clear(self) -> None:
        """Clears all stored events and resets sequence counter."""
        self._events.clear()
        self._counter = 0

    def __len__(self) -> int:
        """Returns the total number of events currently stored."""
        return len(self._events)

    def __bool__(self) -> bool:
        """Repository instance is always truthy regardless of event count."""
        return True
