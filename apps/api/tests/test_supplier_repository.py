import pytest
from app.data.generator import generate_shopflow_dataset
from app.data.scenarios import ScenarioType
from app.domain.supplier import Supplier
from app.repositories.supplier_repository import (
    SupplierRepository,
    SupplierRiskLevel,
    classify_supplier_risk,
)


@pytest.fixture
def repo() -> SupplierRepository:
    """Fixture providing a fresh SupplierRepository with canonical seed 42 dataset."""
    return SupplierRepository()


def test_list_all_suppliers(repo: SupplierRepository):
    suppliers = repo.list_all()
    assert len(suppliers) == 4
    # Check default blueprints
    codes = [s.code for s in suppliers]
    assert "SUP-PAC-01" in codes
    assert "SUP-APX-02" in codes
    assert "SUP-VNG-03" in codes
    assert "SUP-OMN-04" in codes


def test_list_all_deterministic_ordering(repo: SupplierRepository):
    suppliers1 = repo.list_all()
    suppliers2 = repo.list_all()

    # Identical results and ordering across calls
    assert [s.id for s in suppliers1] == [s.id for s in suppliers2]
    # Ordering must be sorted by supplier id
    ids = [s.id for s in suppliers1]
    assert ids == sorted(ids)


def test_get_by_id_success(repo: SupplierRepository):
    supplier = repo.get_by_id("sup-001")
    assert supplier is not None
    assert supplier.id == "sup-001"
    assert supplier.code == "SUP-PAC-01"
    assert supplier.lead_time_days == 10
    assert supplier.reliability == 0.98


def test_get_by_id_unknown(repo: SupplierRepository):
    assert repo.get_by_id("sup-nonexistent-999") is None
    assert repo.get_by_id("") is None


def test_get_by_code_success(repo: SupplierRepository):
    # Exact match
    supplier = repo.get_by_code("SUP-PAC-01")
    assert supplier is not None
    assert supplier.id == "sup-001"

    # Case-insensitive match
    supplier_lower = repo.get_by_code("sup-pac-01")
    assert supplier_lower is not None
    assert supplier_lower.id == "sup-001"


def test_get_by_code_unknown(repo: SupplierRepository):
    assert repo.get_by_code("UNKNOWN-CODE") is None
    assert repo.get_by_code("") is None


def test_active_supplier_filtering():
    # Construct a dataset with mixed active/inactive suppliers
    dataset = generate_shopflow_dataset(seed=42)
    # Mark one supplier as inactive
    dataset.suppliers[1] = dataset.suppliers[1].model_copy(update={"active": False})

    mixed_repo = SupplierRepository(dataset=dataset)
    all_suppliers = mixed_repo.list_all(active_only=False)
    active_suppliers = mixed_repo.get_active_suppliers()

    assert len(all_suppliers) == 4
    assert len(active_suppliers) == 3
    assert all(s.active for s in active_suppliers)
    assert not any(s.id == dataset.suppliers[1].id for s in active_suppliers)


def test_supplier_exists_and_code_exists(repo: SupplierRepository):
    assert repo.supplier_exists("sup-001") is True
    assert repo.supplier_exists("sup-999") is False

    assert repo.code_exists("SUP-PAC-01") is True
    assert repo.code_exists("sup-pac-01") is True
    assert repo.code_exists("SUP-UNKNOWN") is False


def test_supplier_risk_classification():
    # Dependable profile -> LOW
    assert classify_supplier_risk(lead_time_days=8, reliability=0.94, active=True) == SupplierRiskLevel.LOW
    assert classify_supplier_risk(lead_time_days=7, reliability=0.97, active=True) == SupplierRiskLevel.LOW
    assert classify_supplier_risk(lead_time_days=14, reliability=0.92, active=True) == SupplierRiskLevel.LOW

    # Moderate lead time (15–21 days) -> MEDIUM
    assert classify_supplier_risk(lead_time_days=15, reliability=0.95, active=True) == SupplierRiskLevel.MEDIUM
    assert classify_supplier_risk(lead_time_days=20, reliability=0.96, active=True) == SupplierRiskLevel.MEDIUM

    # Moderate reliability (0.85–0.91) -> MEDIUM
    assert classify_supplier_risk(lead_time_days=10, reliability=0.90, active=True) == SupplierRiskLevel.MEDIUM
    assert classify_supplier_risk(lead_time_days=12, reliability=0.88, active=True) == SupplierRiskLevel.MEDIUM

    # High risk: lead time > 21 days
    assert classify_supplier_risk(lead_time_days=22, reliability=0.98, active=True) == SupplierRiskLevel.HIGH
    assert classify_supplier_risk(lead_time_days=55, reliability=0.98, active=True) == SupplierRiskLevel.HIGH

    # High risk: reliability < 0.85
    assert classify_supplier_risk(lead_time_days=7, reliability=0.80, active=True) == SupplierRiskLevel.HIGH
    assert classify_supplier_risk(lead_time_days=10, reliability=0.55, active=True) == SupplierRiskLevel.HIGH

    # High risk: inactive
    assert classify_supplier_risk(lead_time_days=7, reliability=0.98, active=False) == SupplierRiskLevel.HIGH


def test_repo_get_supplier_risk(repo: SupplierRepository):
    s1 = repo.get_by_id("sup-001")  # lead 10, rel 0.98 -> LOW
    assert s1 is not None
    assert repo.get_supplier_risk(s1) == SupplierRiskLevel.LOW


def test_supplier_risk_in_scenarios():
    # Scenario: SUPPLIER_DELAY
    delay_dataset = generate_shopflow_dataset(seed=42, scenario=ScenarioType.SUPPLIER_DELAY)
    delay_repo = SupplierRepository(dataset=delay_dataset)
    affected_sup = delay_repo.get_by_id("sup-001")
    assert affected_sup is not None
    assert affected_sup.lead_time_days == 10 + 45  # 55 days
    assert delay_repo.get_supplier_risk(affected_sup) == SupplierRiskLevel.HIGH

    # Scenario: SUPPLIER_UNRELIABLE
    unreliable_dataset = generate_shopflow_dataset(seed=42, scenario=ScenarioType.SUPPLIER_UNRELIABLE)
    unreliable_repo = SupplierRepository(dataset=unreliable_dataset)
    affected_sup2 = unreliable_repo.get_by_id("sup-001")
    assert affected_sup2 is not None
    assert affected_sup2.reliability == 0.55
    assert unreliable_repo.get_supplier_risk(affected_sup2) == SupplierRiskLevel.HIGH


def test_repeated_calls_produce_identical_results(repo: SupplierRepository):
    res1 = repo.list_all()
    res2 = repo.list_all()
    assert [s.model_dump() for s in res1] == [s.model_dump() for s in res2]

    s1 = repo.get_by_id("sup-002")
    s2 = repo.get_by_id("sup-002")
    assert s1 is not None and s2 is not None
    assert s1.model_dump() == s2.model_dump()
