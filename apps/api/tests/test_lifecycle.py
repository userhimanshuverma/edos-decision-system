import pytest

from app.domain.decision import Decision, DecisionStatus
from app.lifecycle.service import (
    ALLOWED_TRANSITIONS,
    LIFECYCLE_ORDER,
    DecisionLifecycleService,
    InvalidLifecycleTransitionError,
    normalize_status,
)


@pytest.fixture
def lifecycle_service() -> DecisionLifecycleService:
    return DecisionLifecycleService()


def test_lifecycle_order_sequence():
    """Verifies the canonical six-state lifecycle progression sequence."""
    assert LIFECYCLE_ORDER == (
        DecisionStatus.DRAFT,
        DecisionStatus.CONTEXTUALIZING,
        DecisionStatus.CONSTRUCTING,
        DecisionStatus.VALIDATING,
        DecisionStatus.EVALUATING,
        DecisionStatus.READY,
    )


# ============================================================================
# 1. Permitted Forward Transitions
# ============================================================================


@pytest.mark.parametrize(
    "current,target",
    [
        (DecisionStatus.DRAFT, DecisionStatus.CONTEXTUALIZING),
        (DecisionStatus.CONTEXTUALIZING, DecisionStatus.CONSTRUCTING),
        (DecisionStatus.CONSTRUCTING, DecisionStatus.VALIDATING),
        (DecisionStatus.VALIDATING, DecisionStatus.EVALUATING),
        (DecisionStatus.EVALUATING, DecisionStatus.READY),
    ],
)
def test_permitted_forward_transitions(
    lifecycle_service: DecisionLifecycleService,
    current: DecisionStatus,
    target: DecisionStatus,
):
    """Verifies that every sequential forward transition is valid."""
    assert lifecycle_service.is_valid_transition(current, target) is True
    # Should not raise
    lifecycle_service.validate_transition(current, target)


def test_get_allowed_transitions_for_each_state(
    lifecycle_service: DecisionLifecycleService,
):
    """Verifies get_allowed_transitions returns the exact expected target for each status."""
    assert lifecycle_service.get_allowed_transitions(DecisionStatus.DRAFT) == [
        DecisionStatus.CONTEXTUALIZING
    ]
    assert lifecycle_service.get_allowed_transitions(DecisionStatus.CONTEXTUALIZING) == [
        DecisionStatus.CONSTRUCTING
    ]
    assert lifecycle_service.get_allowed_transitions(DecisionStatus.CONSTRUCTING) == [
        DecisionStatus.VALIDATING
    ]
    assert lifecycle_service.get_allowed_transitions(DecisionStatus.VALIDATING) == [
        DecisionStatus.EVALUATING
    ]
    assert lifecycle_service.get_allowed_transitions(DecisionStatus.EVALUATING) == [
        DecisionStatus.READY
    ]
    assert lifecycle_service.get_allowed_transitions(DecisionStatus.READY) == []


# ============================================================================
# 2. Forbidden Stage-Skipping Transitions
# ============================================================================


@pytest.mark.parametrize(
    "current,target",
    [
        (DecisionStatus.DRAFT, DecisionStatus.CONSTRUCTING),
        (DecisionStatus.DRAFT, DecisionStatus.VALIDATING),
        (DecisionStatus.DRAFT, DecisionStatus.EVALUATING),
        (DecisionStatus.DRAFT, DecisionStatus.READY),
        (DecisionStatus.CONTEXTUALIZING, DecisionStatus.VALIDATING),
        (DecisionStatus.CONTEXTUALIZING, DecisionStatus.EVALUATING),
        (DecisionStatus.CONTEXTUALIZING, DecisionStatus.READY),
        (DecisionStatus.CONSTRUCTING, DecisionStatus.EVALUATING),
        (DecisionStatus.CONSTRUCTING, DecisionStatus.READY),
        (DecisionStatus.VALIDATING, DecisionStatus.READY),
    ],
)
def test_forbidden_skipped_stage_transitions(
    lifecycle_service: DecisionLifecycleService,
    current: DecisionStatus,
    target: DecisionStatus,
):
    """Verifies that skipping lifecycle stages is rejected."""
    assert lifecycle_service.is_valid_transition(current, target) is False
    with pytest.raises(InvalidLifecycleTransitionError) as exc_info:
        lifecycle_service.validate_transition(current, target)

    assert exc_info.value.current_status == current
    assert exc_info.value.target_status == target
    assert f"from '{current.value}' to '{target.value}'" in str(exc_info.value)


# ============================================================================
# 3. Forbidden Backward Transitions
# ============================================================================


@pytest.mark.parametrize(
    "current,target",
    [
        (DecisionStatus.CONTEXTUALIZING, DecisionStatus.DRAFT),
        (DecisionStatus.CONSTRUCTING, DecisionStatus.CONTEXTUALIZING),
        (DecisionStatus.CONSTRUCTING, DecisionStatus.DRAFT),
        (DecisionStatus.VALIDATING, DecisionStatus.CONSTRUCTING),
        (DecisionStatus.VALIDATING, DecisionStatus.CONTEXTUALIZING),
        (DecisionStatus.VALIDATING, DecisionStatus.DRAFT),
        (DecisionStatus.EVALUATING, DecisionStatus.VALIDATING),
        (DecisionStatus.EVALUATING, DecisionStatus.CONSTRUCTING),
        (DecisionStatus.EVALUATING, DecisionStatus.CONTEXTUALIZING),
        (DecisionStatus.EVALUATING, DecisionStatus.DRAFT),
        (DecisionStatus.READY, DecisionStatus.EVALUATING),
        (DecisionStatus.READY, DecisionStatus.VALIDATING),
        (DecisionStatus.READY, DecisionStatus.CONSTRUCTING),
        (DecisionStatus.READY, DecisionStatus.CONTEXTUALIZING),
        (DecisionStatus.READY, DecisionStatus.DRAFT),
    ],
)
def test_forbidden_backward_transitions(
    lifecycle_service: DecisionLifecycleService,
    current: DecisionStatus,
    target: DecisionStatus,
):
    """Verifies that backward transitions are strictly forbidden."""
    assert lifecycle_service.is_valid_transition(current, target) is False
    with pytest.raises(InvalidLifecycleTransitionError) as exc_info:
        lifecycle_service.validate_transition(current, target)

    assert exc_info.value.current_status == current
    assert exc_info.value.target_status == target


# ============================================================================
# 4. Same-State Transitions (Forbidden)
# ============================================================================


@pytest.mark.parametrize(
    "status",
    [
        DecisionStatus.DRAFT,
        DecisionStatus.CONTEXTUALIZING,
        DecisionStatus.CONSTRUCTING,
        DecisionStatus.VALIDATING,
        DecisionStatus.EVALUATING,
        DecisionStatus.READY,
    ],
)
def test_same_state_transitions_rejected(
    lifecycle_service: DecisionLifecycleService,
    status: DecisionStatus,
):
    """Verifies that transitioning to the same state is rejected as invalid."""
    assert lifecycle_service.is_valid_transition(status, status) is False
    with pytest.raises(InvalidLifecycleTransitionError) as exc_info:
        lifecycle_service.validate_transition(status, status)

    assert exc_info.value.current_status == status
    assert exc_info.value.target_status == status


# ============================================================================
# 5. Terminal State (READY) Transitions
# ============================================================================


@pytest.mark.parametrize("target", list(DecisionStatus))
def test_transitions_from_ready_all_rejected(
    lifecycle_service: DecisionLifecycleService,
    target: DecisionStatus,
):
    """Verifies that no transitions can be made out of the terminal READY state."""
    assert lifecycle_service.is_valid_transition(DecisionStatus.READY, target) is False
    with pytest.raises(InvalidLifecycleTransitionError):
        lifecycle_service.validate_transition(DecisionStatus.READY, target)


# ============================================================================
# 6. Unknown and Malformed Status Values
# ============================================================================


def test_unknown_status_normalization_raises_value_error():
    """Verifies that unknown status strings raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        normalize_status("NONEXISTENT_STATUS")
    assert "Unknown decision status" in str(exc_info.value)


def test_is_valid_transition_returns_false_for_unknown_string(
    lifecycle_service: DecisionLifecycleService,
):
    """Verifies is_valid_transition returns False when encountering invalid strings."""
    assert lifecycle_service.is_valid_transition("DRAFT", "INVALID") is False
    assert lifecycle_service.is_valid_transition("INVALID", "DRAFT") is False


# ============================================================================
# 7. Domain Model Immutability on Transition
# ============================================================================


def test_transition_domain_model_immutability(
    lifecycle_service: DecisionLifecycleService,
):
    """Verifies that transition returns a new Decision instance and preserves the original."""
    original = Decision(
        id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
    )

    updated = lifecycle_service.transition(original, DecisionStatus.CONTEXTUALIZING)

    # Updated has new status
    assert updated.status == DecisionStatus.CONTEXTUALIZING
    assert updated.id == original.id
    assert updated.product_id == original.product_id
    assert updated.warehouse_id == original.warehouse_id
    assert updated.created_at == original.created_at

    # Original is untouched
    assert original.status == DecisionStatus.DRAFT


def test_transition_domain_model_invalid_raises_and_preserves(
    lifecycle_service: DecisionLifecycleService,
):
    """Verifies invalid transition raises error and does not mutate input entity."""
    original = Decision(
        id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
    )

    with pytest.raises(InvalidLifecycleTransitionError):
        lifecycle_service.transition(original, DecisionStatus.READY)

    assert original.status == DecisionStatus.DRAFT
