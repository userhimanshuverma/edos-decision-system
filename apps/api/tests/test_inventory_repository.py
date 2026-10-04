import pytest

from app.data import generate_shopflow_dataset
from app.domain import Inventory
from app.repositories.inventory_repository import InventoryRepository


def test_repository_default_initialization():
    repo = InventoryRepository()
    assert repo.dataset.seed == 42
    # 10 products x 3 warehouses = 30 inventory positions
    all_inventory = repo.list_all()
    assert len(all_inventory) == 30
    for inv in all_inventory:
        assert isinstance(inv, Inventory)


def test_repository_custom_dataset_injection():
    custom_dataset = generate_shopflow_dataset(seed=99, product_count=4, warehouse_count=2)
    repo = InventoryRepository(dataset=custom_dataset)
    assert repo.dataset.seed == 99
    assert len(repo.list_all()) == 8


def test_repository_get_by_id():
    repo = InventoryRepository()
    all_inv = repo.list_all()
    first_item = all_inv[0]

    found = repo.get_by_id(first_item.id)
    assert found is not None
    assert found.id == first_item.id
    assert found.product_id == first_item.product_id
    assert found.warehouse_id == first_item.warehouse_id

    missing = repo.get_by_id("non-existent-inventory-id")
    assert missing is None


def test_repository_get_by_product_id():
    repo = InventoryRepository()
    product_id = "prod-001"

    records = repo.get_by_product_id(product_id)
    # Default dataset has 3 warehouses, so 3 positions per product
    assert len(records) == 3
    for inv in records:
        assert inv.product_id == product_id

    empty_records = repo.get_by_product_id("non-existent-product")
    assert empty_records == []


def test_repository_get_by_warehouse_id():
    repo = InventoryRepository()
    warehouse_id = "wh-001"

    records = repo.get_by_warehouse_id(warehouse_id)
    # Default dataset has 10 products, so 10 positions in warehouse 1
    assert len(records) == 10
    for inv in records:
        assert inv.warehouse_id == warehouse_id

    empty_records = repo.get_by_warehouse_id("non-existent-warehouse")
    assert empty_records == []


def test_repository_list_all_filtering():
    repo = InventoryRepository()
    # Filter by product
    by_prod = repo.list_all(product_id="prod-002")
    assert len(by_prod) == 3

    # Filter by warehouse
    by_wh = repo.list_all(warehouse_id="wh-002")
    assert len(by_wh) == 10

    # Combined filter: exactly 1 position
    by_both = repo.list_all(product_id="prod-002", warehouse_id="wh-002")
    assert len(by_both) == 1
    assert by_both[0].product_id == "prod-002"
    assert by_both[0].warehouse_id == "wh-002"

    # Non-matching filter returns empty list
    by_none = repo.list_all(product_id="non-existent")
    assert by_none == []


def test_repository_existence_checks():
    repo = InventoryRepository()
    assert repo.product_exists("prod-001") is True
    assert repo.product_exists("prod-999") is False

    assert repo.warehouse_exists("wh-001") is True
    assert repo.warehouse_exists("wh-999") is False


def test_repository_data_integrity():
    repo = InventoryRepository()
    all_inventory = repo.list_all()

    for inv in all_inventory:
        assert repo.product_exists(inv.product_id) is True
        assert repo.warehouse_exists(inv.warehouse_id) is True
        assert inv.quantity_reserved <= inv.quantity_on_hand
        assert inv.available_quantity == inv.quantity_on_hand - inv.quantity_reserved
        assert inv.available_quantity >= 0
