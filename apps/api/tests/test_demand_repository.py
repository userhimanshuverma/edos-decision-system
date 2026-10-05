import datetime as dt
import pytest

from app.data import generate_shopflow_dataset
from app.domain.demand import DemandRecord
from app.repositories.demand_repository import DemandRepository


def test_repository_default_initialization():
    repo = DemandRepository()
    assert repo.dataset.seed == 42
    # Default: 10 products x 3 warehouses x 14 days = 420 demand records
    all_demand = repo.list_all()
    assert len(all_demand) == 420
    for record in all_demand:
        assert isinstance(record, DemandRecord)
        assert record.quantity >= 0


def test_repository_custom_dataset_injection():
    custom_dataset = generate_shopflow_dataset(
        seed=123,
        product_count=4,
        warehouse_count=2,
        demand_days=7,
    )
    repo = DemandRepository(dataset=custom_dataset)
    assert repo.dataset.seed == 123
    # 4 products x 2 warehouses x 7 days = 56 records
    assert len(repo.list_all()) == 56


def test_repository_get_by_id():
    repo = DemandRepository()
    all_records = repo.list_all()
    first_record = all_records[0]

    found = repo.get_by_id(first_record.id)
    assert found is not None
    assert found.id == first_record.id
    assert found.product_id == first_record.product_id
    assert found.warehouse_id == first_record.warehouse_id
    assert found.date == first_record.date
    assert found.quantity == first_record.quantity

    missing = repo.get_by_id("non-existent-demand-id")
    assert missing is None


def test_repository_get_by_product_id():
    repo = DemandRepository()
    product_id = "prod-001"

    records = repo.get_by_product_id(product_id)
    # 3 warehouses x 14 days = 42 records per product
    assert len(records) == 42
    for r in records:
        assert r.product_id == product_id

    empty_records = repo.get_by_product_id("non-existent-product")
    assert empty_records == []


def test_repository_get_by_warehouse_id():
    repo = DemandRepository()
    warehouse_id = "wh-001"

    records = repo.get_by_warehouse_id(warehouse_id)
    # 10 products x 14 days = 140 records per warehouse
    assert len(records) == 140
    for r in records:
        assert r.warehouse_id == warehouse_id

    empty_records = repo.get_by_warehouse_id("non-existent-warehouse")
    assert empty_records == []


def test_repository_get_by_product_and_warehouse():
    repo = DemandRepository()
    product_id = "prod-001"
    warehouse_id = "wh-001"

    records = repo.get_by_product_and_warehouse(product_id, warehouse_id)
    # 14 days of records for a single product at a single warehouse
    assert len(records) == 14
    for r in records:
        assert r.product_id == product_id
        assert r.warehouse_id == warehouse_id


def test_repository_get_by_date_range():
    repo = DemandRepository()
    all_records = repo.list_all()
    all_dates = sorted({r.date for r in all_records})

    start_date = all_dates[2]
    end_date = all_dates[5]

    filtered = repo.get_by_date_range(start_date=start_date, end_date=end_date)
    # 4 distinct dates x 10 products x 3 warehouses = 120 records
    assert len(filtered) == 120
    for r in filtered:
        assert start_date <= r.date <= end_date


def test_repository_list_all_filtering():
    repo = DemandRepository()
    all_records = repo.list_all()
    all_dates = sorted({r.date for r in all_records})

    # Combined filter: product + warehouse + date range
    sub = repo.list_all(
        product_id="prod-002",
        warehouse_id="wh-002",
        start_date=all_dates[0],
        end_date=all_dates[4],
    )
    assert len(sub) == 5
    for r in sub:
        assert r.product_id == "prod-002"
        assert r.warehouse_id == "wh-002"
        assert all_dates[0] <= r.date <= all_dates[4]


def test_repository_existence_checks():
    repo = DemandRepository()
    assert repo.product_exists("prod-001") is True
    assert repo.product_exists("ghost-prod-999") is False
    assert repo.warehouse_exists("wh-001") is True
    assert repo.warehouse_exists("ghost-wh-999") is False


def test_repository_trend_aggregation():
    repo = DemandRepository()
    product_id = "prod-001"

    trend = repo.get_product_demand_trend(product_id=product_id)
    assert trend["product_id"] == product_id
    assert trend["warehouse_id"] is None
    assert trend["total_demand"] > 0
    assert trend["average_daily_demand"] > 0.0
    assert trend["trend_direction"] in {"increasing", "decreasing", "stable"}
    assert isinstance(trend["percentage_change"], float)
    assert len(trend["history"]) == 14

    # Verify history is chronologically ordered
    dates = [p["date"] for p in trend["history"]]
    assert dates == sorted(dates)

    # Filtered by warehouse
    wh_trend = repo.get_product_demand_trend(product_id=product_id, warehouse_id="wh-001")
    assert wh_trend["warehouse_id"] == "wh-001"
    assert len(wh_trend["history"]) == 14
    assert wh_trend["total_demand"] <= trend["total_demand"]


def test_repository_trend_empty_and_boundary():
    repo = DemandRepository()
    # Unknown product with no records
    trend = repo.get_product_demand_trend(product_id="non-existent")
    assert trend["total_demand"] == 0
    assert trend["average_daily_demand"] == 0.0
    assert trend["trend_direction"] == "stable"
    assert trend["percentage_change"] == 0.0
    assert trend["history"] == []
