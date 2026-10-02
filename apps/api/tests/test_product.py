import json
import pytest
from pydantic import ValidationError
from app.domain.product import Product


def test_valid_product():
    product = Product(
        id="prod-001",
        sku="SKU-CHAIR-BLK",
        name="Ergonomic Office Chair",
        category="Furniture",
        unit_cost=120.50,
        selling_price=249.99,
        reorder_point=15,
        active=True,
    )
    assert product.id == "prod-001"
    assert product.sku == "SKU-CHAIR-BLK"
    assert product.name == "Ergonomic Office Chair"
    assert product.category == "Furniture"
    assert product.unit_cost == 120.50
    assert product.selling_price == 249.99
    assert product.reorder_point == 15
    assert product.active is True


def test_product_default_active():
    product = Product(
        id="prod-002",
        sku="SKU-DESK-OAK",
        name="Oak Standing Desk",
        category="Furniture",
        unit_cost=300.00,
        selling_price=599.00,
        reorder_point=5,
    )
    assert product.active is True


def test_product_required_fields():
    with pytest.raises(ValidationError) as exc_info:
        Product(
            id="prod-003",
            # sku missing
            name="Oak Desk",
            category="Furniture",
            unit_cost=300.00,
            selling_price=599.00,
            reorder_point=5,
        )
    assert "sku" in str(exc_info.value)


def test_product_empty_or_whitespace_strings():
    with pytest.raises(ValidationError):
        Product(
            id="",
            sku="SKU-TEST",
            name="Test",
            category="Test",
            unit_cost=10.0,
            selling_price=20.0,
            reorder_point=5,
        )

    with pytest.raises(ValidationError):
        Product(
            id="prod-004",
            sku="   ",
            name="Test",
            category="Test",
            unit_cost=10.0,
            selling_price=20.0,
            reorder_point=5,
        )


def test_product_negative_unit_cost():
    with pytest.raises(ValidationError) as exc_info:
        Product(
            id="prod-005",
            sku="SKU-TEST",
            name="Test",
            category="Test",
            unit_cost=-1.0,
            selling_price=20.0,
            reorder_point=5,
        )
    assert "unit_cost" in str(exc_info.value)


def test_product_negative_selling_price():
    with pytest.raises(ValidationError) as exc_info:
        Product(
            id="prod-006",
            sku="SKU-TEST",
            name="Test",
            category="Test",
            unit_cost=10.0,
            selling_price=-0.01,
            reorder_point=5,
        )
    assert "selling_price" in str(exc_info.value)


def test_product_negative_reorder_point():
    with pytest.raises(ValidationError) as exc_info:
        Product(
            id="prod-007",
            sku="SKU-TEST",
            name="Test",
            category="Test",
            unit_cost=10.0,
            selling_price=20.0,
            reorder_point=-5,
        )
    assert "reorder_point" in str(exc_info.value)


def test_product_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        Product(
            id="prod-008",
            sku="SKU-TEST",
            name="Test",
            category="Test",
            unit_cost=10.0,
            selling_price=20.0,
            reorder_point=5,
            unexpected_field="invalid",
        )


def test_product_serialization():
    payload = {
        "id": "prod-009",
        "sku": "SKU-MONITOR-4K",
        "name": "4K Ultra-Wide Monitor",
        "category": "Electronics",
        "unit_cost": 350.0,
        "selling_price": 699.99,
        "reorder_point": 10,
        "active": True,
    }
    product = Product.model_validate(payload)
    assert product.sku == "SKU-MONITOR-4K"

    # Test dictionary serialization
    dumped_dict = product.model_dump()
    assert dumped_dict == payload

    # Test JSON round-trip
    dumped_json = product.model_dump_json()
    parsed_json = json.loads(dumped_json)
    assert parsed_json["sku"] == "SKU-MONITOR-4K"
    assert parsed_json["selling_price"] == 699.99

    recreated = Product.model_validate_json(dumped_json)
    assert recreated == product
