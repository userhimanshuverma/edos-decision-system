from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.data.dataset import ShopFlowDataset
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    CandidateActionType,
    DoNothingParameters,
    IneligibleSupplierError,
    PlaceOrderParameters,
    SupplierNotFoundError,
    SwitchSupplierParameters,
    validate_supplier_eligibility,
)
from app.domain.supplier import Supplier


def test_valid_do_nothing_action():
    """Verifies that a valid DO_NOTHING candidate action can be instantiated."""
    action = CandidateAction(
        id="ACT-0001",
        decision_id="DEC-0001",
        action_type=ActionType.DO_NOTHING,
        parameters={},
        description="Maintain current inventory posture without reorder",
    )
    assert action.id == "ACT-0001"
    assert action.action_id == "ACT-0001"
    assert action.decision_id == "DEC-0001"
    assert action.action_type == ActionType.DO_NOTHING
    assert action.type == ActionType.DO_NOTHING
    assert isinstance(action.parameters, DoNothingParameters)
    assert action.description == "Maintain current inventory posture without reorder"
    assert isinstance(action.created_at, datetime)
    assert action.created_at.tzinfo == timezone.utc


def test_valid_place_order_action():
    """Verifies that a valid PLACE_ORDER candidate action can be instantiated with positive quantity."""
    action = CandidateAction(
        id="ACT-0002",
        decision_id="DEC-0001",
        action_type=ActionType.PLACE_ORDER,
        parameters={"quantity": 150},
        description="Replenish stock to cover projected 30-day demand",
    )
    assert action.id == "ACT-0002"
    assert action.decision_id == "DEC-0001"
    assert action.action_type == ActionType.PLACE_ORDER
    assert isinstance(action.parameters, PlaceOrderParameters)
    assert action.parameters.quantity == 150
    assert action.parameters.order_quantity == 150


def test_valid_switch_supplier_action():
    """Verifies that a valid SWITCH_SUPPLIER candidate action can be instantiated with target supplier."""
    action = CandidateAction(
        id="ACT-0003",
        decision_id="DEC-0001",
        action_type=ActionType.SWITCH_SUPPLIER,
        parameters={"target_supplier_id": "sup-002"},
        description="Switch to secondary active supplier with shorter lead time",
    )
    assert action.id == "ACT-0003"
    assert action.decision_id == "DEC-0001"
    assert action.action_type == ActionType.SWITCH_SUPPLIER
    assert isinstance(action.parameters, SwitchSupplierParameters)
    assert action.parameters.target_supplier_id == "sup-002"
    assert action.parameters.supplier_id == "sup-002"


def test_action_aliases_and_string_action_type():
    """Verifies string values for action_type and parameter aliases work correctly."""
    # Using 'type' alias and string enum value
    a1 = CandidateAction(
        id="ACT-0004",
        decision_id="DEC-0001",
        type="PLACE_ORDER",
        parameters={"order_quantity": 75},
    )
    assert a1.action_type == ActionType.PLACE_ORDER
    assert isinstance(a1.parameters, PlaceOrderParameters)
    assert a1.parameters.quantity == 75

    # Using 'supplier_id' alias for switch supplier
    a2 = CandidateAction(
        id="ACT-0005",
        decision_id="DEC-0001",
        type="SWITCH_SUPPLIER",
        parameters={"supplier_id": "sup-003"},
    )
    assert a2.action_type == ActionType.SWITCH_SUPPLIER
    assert isinstance(a2.parameters, SwitchSupplierParameters)
    assert a2.parameters.target_supplier_id == "sup-003"


def test_place_order_quantity_validation():
    """Verifies that non-positive quantities are rejected for PLACE_ORDER."""
    # Zero quantity rejected
    with pytest.raises(ValidationError) as exc_info:
        CandidateAction(
            id="ACT-0006",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters={"quantity": 0},
        )
    assert "greater than 0" in str(exc_info.value) or "gt" in str(exc_info.value)

    # Negative quantity rejected
    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0007",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters={"quantity": -50},
        )

    # Missing quantity rejected
    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0008",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters={},
        )


def test_switch_supplier_target_supplier_validation():
    """Verifies that empty or whitespace-only target_supplier_id is rejected."""
    # Missing target_supplier_id
    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0009",
            decision_id="DEC-0001",
            action_type=ActionType.SWITCH_SUPPLIER,
            parameters={},
        )

    # Empty string
    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0010",
            decision_id="DEC-0001",
            action_type=ActionType.SWITCH_SUPPLIER,
            parameters={"target_supplier_id": ""},
        )

    # Whitespace-only string
    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0011",
            decision_id="DEC-0001",
            action_type=ActionType.SWITCH_SUPPLIER,
            parameters={"target_supplier_id": "   "},
        )


def test_do_nothing_rejects_extraneous_parameters():
    """Verifies that DO_NOTHING rejects irrelevant order or supplier parameters."""
    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0012",
            decision_id="DEC-0001",
            action_type=ActionType.DO_NOTHING,
            parameters={"quantity": 100},
        )

    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0013",
            decision_id="DEC-0001",
            action_type=ActionType.DO_NOTHING,
            parameters={"target_supplier_id": "sup-001"},
        )


def test_action_rejects_mismatched_parameters():
    """Verifies that providing wrong parameter types for an action type is rejected."""
    # Place order with switch supplier parameters
    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0014",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters={"target_supplier_id": "sup-002"},
        )

    # Switch supplier with place order parameters
    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0015",
            decision_id="DEC-0001",
            action_type=ActionType.SWITCH_SUPPLIER,
            parameters={"quantity": 100},
        )


def test_candidate_action_extra_fields_forbidden():
    """Verifies that unexpected out-of-scope fields are rejected on CandidateAction."""
    with pytest.raises(ValidationError) as exc_info:
        CandidateAction(
            id="ACT-0016",
            decision_id="DEC-0001",
            action_type=ActionType.DO_NOTHING,
            parameters={},
            recommended=True,  # Out-of-scope for Day 16
        )
    assert "extra_forbidden" in str(exc_info.value) or "recommended" in str(exc_info.value)

    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0017",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters={"quantity": 100},
            score=98.5,  # Out-of-scope for Day 16
        )


def test_non_empty_identifiers():
    """Verifies that empty or whitespace identifiers are rejected."""
    # Empty id
    with pytest.raises(ValidationError):
        CandidateAction(
            id="",
            decision_id="DEC-0001",
            action_type=ActionType.DO_NOTHING,
            parameters={},
        )

    # Whitespace id
    with pytest.raises(ValidationError):
        CandidateAction(
            id="   ",
            decision_id="DEC-0001",
            action_type=ActionType.DO_NOTHING,
            parameters={},
        )

    # Empty decision_id
    with pytest.raises(ValidationError):
        CandidateAction(
            id="ACT-0018",
            decision_id="",
            action_type=ActionType.DO_NOTHING,
            parameters={},
        )


def test_supplier_reference_validation():
    """Verifies supplier existence and eligibility validation logic."""
    active_sup = Supplier(
        id="sup-active",
        code="SUP-ACT",
        name="Active Supplier Inc",
        lead_time_days=7,
        reliability=0.98,
        active=True,
    )
    inactive_sup = Supplier(
        id="sup-inactive",
        code="SUP-INACT",
        name="Inactive Supplier Ltd",
        lead_time_days=14,
        reliability=0.70,
        active=False,
    )
    dataset = ShopFlowDataset(
        seed=42,
        suppliers=[active_sup, inactive_sup],
    )

    # 1. Active existing supplier is eligible
    result = validate_supplier_eligibility("sup-active", dataset=dataset)
    assert result.id == "sup-active"
    assert result.active is True

    # 2. Inactive existing supplier is rejected as ineligible
    with pytest.raises(IneligibleSupplierError) as exc_info:
        validate_supplier_eligibility("sup-inactive", dataset=dataset)
    assert "inactive" in str(exc_info.value)

    # 3. Nonexistent supplier is rejected
    with pytest.raises(SupplierNotFoundError) as exc_info:
        validate_supplier_eligibility("sup-nonexistent", dataset=dataset)
    assert "not found" in str(exc_info.value)

    # 4. Empty supplier ID is rejected
    with pytest.raises(SupplierNotFoundError):
        validate_supplier_eligibility("", dataset=dataset)


def test_serialization_and_round_trip():
    """Verifies stable JSON serialization and round-trip deserialization."""
    original = CandidateAction(
        id="ACT-0020",
        decision_id="DEC-0001",
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=250),
        description="Bulk order for warehouse safety stock",
        metadata={"priority": "standard"},
    )
    serialized = original.model_dump(mode="json")
    assert serialized["id"] == "ACT-0020"
    assert serialized["decision_id"] == "DEC-0001"
    assert serialized["action_type"] == "PLACE_ORDER"
    assert serialized["parameters"] == {"quantity": 250}
    assert serialized["metadata"] == {"priority": "standard"}

    deserialized = CandidateAction.model_validate(serialized)
    assert deserialized.id == original.id
    assert deserialized.decision_id == original.decision_id
    assert deserialized.action_type == original.action_type
    assert isinstance(deserialized.parameters, PlaceOrderParameters)
    assert deserialized.parameters.quantity == 250
    assert deserialized.description == original.description
    assert deserialized.metadata == original.metadata
