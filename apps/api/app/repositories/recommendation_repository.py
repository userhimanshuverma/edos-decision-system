from __future__ import annotations

from typing import Sequence
from app.domain.recommendation import Recommendation


class DuplicateRecommendationError(ValueError):
    """Raised when attempting to store a recommendation with an identifier that already exists."""


class RecommendationRepository:
    """In-memory repository for business decision recommendations.

    Provides deterministic storage, retrieval, ordering, and duplicate protection
    for recommendations selected from evaluated candidate actions.

    Guarantees:
    - Stable sequential identifier generation (REC-XXXX).
    - Deep defensive copies on write and read paths.
    - Decision isolation: queries filtered by decision return strictly that decision's recommendations.
    - Deterministic ordering: sorted primarily by created_at ascending, secondarily by recommendation id ascending.
    """

    def __init__(self, recommendations: Sequence[Recommendation] | None = None) -> None:
        """Initializes the repository with an empty store or preloaded recommendations."""
        self._recommendations: dict[str, Recommendation] = {}
        self._counter: int = 0

        if recommendations:
            for rec in recommendations:
                self.record(rec)

    def generate_id(self) -> str:
        """Generates the next unique recommendation identifier (REC-XXXX)."""
        while True:
            self._counter += 1
            candidate = f"REC-{self._counter:04d}"
            if candidate not in self._recommendations:
                return candidate

    def record(self, recommendation: Recommendation) -> Recommendation:
        """Stores a validated Recommendation in memory.

        Raises:
            DuplicateRecommendationError: If a recommendation with this ID already exists.

        Returns a defensive deep copy of the stored recommendation.
        """
        norm_id = recommendation.id.strip()
        if norm_id in self._recommendations:
            raise DuplicateRecommendationError(
                f"Recommendation with identifier '{recommendation.id}' already exists"
            )

        defensive_copy = recommendation.model_copy(deep=True)
        self._recommendations[norm_id] = defensive_copy
        return defensive_copy.model_copy(deep=True)

    def get_by_id(self, recommendation_id: str) -> Recommendation | None:
        """Retrieves a recommendation by unique identifier. Returns defensive copy or None."""
        norm_id = recommendation_id.strip()
        rec = self._recommendations.get(norm_id)
        if rec is None:
            return None
        return rec.model_copy(deep=True)

    def get_latest_for_decision(self, decision_id: str) -> Recommendation | None:
        """Retrieves the latest recommendation generated for a specific business decision."""
        recs = self.list_by_decision_id(decision_id)
        if not recs:
            return None
        return recs[-1].model_copy(deep=True)

    def list_by_decision_id(self, decision_id: str) -> list[Recommendation]:
        """Returns all recommendations for a decision, sorted deterministically by (created_at, id)."""
        norm_decision_id = decision_id.strip()
        matching = [
            rec for rec in self._recommendations.values()
            if rec.decision_id == norm_decision_id
        ]
        matching.sort(key=lambda r: (r.created_at, r.id))
        return [r.model_copy(deep=True) for r in matching]

    def list_all(self, decision_id: str | None = None) -> list[Recommendation]:
        """Returns all stored recommendations or recommendations filtered by decision_id."""
        if decision_id is not None:
            return self.list_by_decision_id(decision_id)
        all_recs = list(self._recommendations.values())
        all_recs.sort(key=lambda r: (r.created_at, r.id))
        return [r.model_copy(deep=True) for r in all_recs]

    def remove(self, recommendation_id: str) -> bool:
        """Removes a stored recommendation by ID. Returns True if removed, False otherwise."""
        norm_id = recommendation_id.strip()
        return self._recommendations.pop(norm_id, None) is not None

    def clear(self) -> None:
        """Clears all stored recommendations and resets sequential ID counter."""
        self._recommendations.clear()
        self._counter = 0

    def __len__(self) -> int:
        return len(self._recommendations)
