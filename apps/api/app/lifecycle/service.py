from __future__ import annotations

from typing import Sequence

from app.domain.decision import Decision, DecisionStatus


class InvalidLifecycleTransitionError(ValueError):
    """Raised when an invalid lifecycle status transition is attempted."""

    def __init__(
        self,
        current_status: DecisionStatus,
        target_status: DecisionStatus,
        message: str | None = None,
    ) -> None:
        self.current_status = current_status
        self.target_status = target_status
        if message is None:
            allowed = ALLOWED_TRANSITIONS.get(current_status, ())
            allowed_names = [s.value for s in allowed] or ["None"]
            message = (
                f"Invalid lifecycle transition from '{current_status.value}' to '{target_status.value}'. "
                f"Permitted next state(s): {', '.join(allowed_names)}."
            )
        super().__init__(message)


# Alias for compatibility
InvalidStateTransitionError = InvalidLifecycleTransitionError


# Explicit, centralized transition map enforcing strict forward single-step transitions
ALLOWED_TRANSITIONS: dict[DecisionStatus, tuple[DecisionStatus, ...]] = {
    DecisionStatus.DRAFT: (DecisionStatus.CONTEXTUALIZING,),
    DecisionStatus.CONTEXTUALIZING: (DecisionStatus.CONSTRUCTING,),
    DecisionStatus.CONSTRUCTING: (DecisionStatus.VALIDATING,),
    DecisionStatus.VALIDATING: (DecisionStatus.EVALUATING,),
    DecisionStatus.EVALUATING: (DecisionStatus.READY,),
    DecisionStatus.READY: (),
}

# The ordered progression sequence across the lifecycle
LIFECYCLE_ORDER: tuple[DecisionStatus, ...] = (
    DecisionStatus.DRAFT,
    DecisionStatus.CONTEXTUALIZING,
    DecisionStatus.CONSTRUCTING,
    DecisionStatus.VALIDATING,
    DecisionStatus.EVALUATING,
    DecisionStatus.READY,
)


def normalize_status(status_val: DecisionStatus | str) -> DecisionStatus:
    """Ensures input is a valid DecisionStatus enum instance."""
    if isinstance(status_val, DecisionStatus):
        return status_val
    try:
        return DecisionStatus(status_val)
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Unknown decision status: '{status_val}'") from exc


class DecisionLifecycleService:
    """Service enforcing deterministic decision lifecycle state transitions.

    Guarantees strict single-step sequential progression:
    DRAFT -> CONTEXTUALIZING -> CONSTRUCTING -> VALIDATING -> EVALUATING -> READY.

    Enforces that:
    - Stage skipping is rejected (e.g., DRAFT -> READY).
    - Backward transitions are rejected (e.g., VALIDATING -> CONSTRUCTING).
    - Transitions from terminal states are rejected (e.g., READY -> DRAFT).
    - Transitions to the same status are rejected (e.g., DRAFT -> DRAFT).
    - Invalid or unknown statuses are rejected.
    """

    def __init__(
        self,
        allowed_transitions: dict[DecisionStatus, Sequence[DecisionStatus]] | None = None,
    ) -> None:
        if allowed_transitions is not None:
            self._allowed_transitions: dict[DecisionStatus, tuple[DecisionStatus, ...]] = {
                k: tuple(v) for k, v in allowed_transitions.items()
            }
        else:
            self._allowed_transitions = ALLOWED_TRANSITIONS

    def get_allowed_transitions(
        self,
        current_status: DecisionStatus | str,
    ) -> list[DecisionStatus]:
        """Returns the list of permitted target statuses from the current status."""
        current = normalize_status(current_status)
        return list(self._allowed_transitions.get(current, ()))

    def is_valid_transition(
        self,
        current_status: DecisionStatus | str,
        target_status: DecisionStatus | str,
    ) -> bool:
        """Determines whether a transition from current_status to target_status is permitted."""
        try:
            current = normalize_status(current_status)
            target = normalize_status(target_status)
        except ValueError:
            return False
        allowed = self._allowed_transitions.get(current, ())
        return target in allowed

    def validate_transition(
        self,
        current_status: DecisionStatus | str,
        target_status: DecisionStatus | str,
    ) -> None:
        """Validates a status transition, raising InvalidLifecycleTransitionError if forbidden."""
        current = normalize_status(current_status)
        target = normalize_status(target_status)
        if not self.is_valid_transition(current, target):
            raise InvalidLifecycleTransitionError(
                current_status=current,
                target_status=target,
            )

    def transition(
        self,
        decision: Decision,
        target_status: DecisionStatus | str,
    ) -> Decision:
        """Validates and applies a status transition to a Decision domain instance.

        Returns a new Decision instance with the updated status.
        The original Decision instance is never mutated.
        """
        target = normalize_status(target_status)
        self.validate_transition(decision.status, target)
        return decision.model_copy(update={"status": target}, deep=True)
