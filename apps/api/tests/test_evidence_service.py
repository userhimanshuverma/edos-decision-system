from __future__ import annotations

import pytest

from app.domain.candidate_action import ActionType, CandidateAction, PlaceOrderParameters
from app.domain.decision import Decision, DecisionStatus
from app.domain.decision_version import DecisionSnapshot, DecisionVersion
from app.domain.evidence import (
    DecisionAssumption,
    DecisionEvidence,
    EvidenceCategory,
    EvidenceType,
)
from app.domain.inventory import Inventory
from app.domain.product import Product
from app.domain.supplier import Supplier
from app.domain.warehouse import Warehouse
from app.evidence.service import (
    AssumptionNotFoundError,
    CandidateActionNotFoundError,
    CrossDecisionIsolationError,
    DecisionNotFoundError,
    DecisionVersionNotFoundError,
    EvidenceNotFoundError,
    EvidenceService,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import DecisionVersionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository


@pytest.fixture
def decision_repo() -> DecisionRepository:
    repo = DecisionRepository()
    repo.create(Decision(id="DEC-0001", product_id="prod-001", warehouse_id="wh-001", status=DecisionStatus.DRAFT))
    repo.create(Decision(id="DEC-0002", product_id="prod-002", warehouse_id="wh-001", status=DecisionStatus.DRAFT))
    return repo


@pytest.fixture
def action_repo(decision_repo: DecisionRepository) -> CandidateActionRepository:
    repo = CandidateActionRepository()
    repo.record(
        CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )
    )
    repo.record(
        CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0002",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=25),
        )
    )
    return repo


@pytest.fixture
def version_repo() -> DecisionVersionRepository:
    repo = DecisionVersionRepository()
    repo.record(
        DecisionVersion(
            id="VER-0001",
            decision_id="DEC-0001",
            version_number=1,
            snapshot=DecisionSnapshot(
                decision_id="DEC-0001",
                product_id="prod-001",
                warehouse_id="wh-001",
                status=DecisionStatus.DRAFT,
                decision_created_at="2026-10-20T10:00:00Z",
            ),
        )
    )
    return repo


from app.data.generator import generate_shopflow_dataset


@pytest.fixture
def shared_dataset():
    return generate_shopflow_dataset(seed=42)


@pytest.fixture
def inventory_repo(shared_dataset) -> InventoryRepository:
    return InventoryRepository(dataset=shared_dataset)


@pytest.fixture
def supplier_repo(shared_dataset) -> SupplierRepository:
    return SupplierRepository(dataset=shared_dataset)


@pytest.fixture
def demand_repo(shared_dataset) -> DemandRepository:
    return DemandRepository(dataset=shared_dataset)


@pytest.fixture
def service(
    decision_repo: DecisionRepository,
    action_repo: CandidateActionRepository,
    version_repo: DecisionVersionRepository,
    inventory_repo: InventoryRepository,
    supplier_repo: SupplierRepository,
    demand_repo: DemandRepository,
) -> EvidenceService:
    return EvidenceService(
        decision_repo=decision_repo,
        action_repo=action_repo,
        version_repo=version_repo,
        inventory_repo=inventory_repo,
        supplier_repo=supplier_repo,
        demand_repo=demand_repo,
    )


def test_create_and_get_evidence(service: EvidenceService):
    ev = service.create_evidence(
        decision_id="DEC-0001",
        evidence_type=EvidenceType.FACT,
        category=EvidenceCategory.INVENTORY,
        description="Available stock is 40 units",
        value=40,
        unit="units",
        source="inventory:prod-001@wh-001",
        action_id="ACT-0001",
        version_id="VER-0001",
    )
    assert ev.id.startswith("EVD-")
    assert ev.decision_id == "DEC-0001"
    assert ev.value == 40
    assert ev.action_id == "ACT-0001"
    assert ev.version_id == "VER-0001"

    retrieved = service.get_evidence("DEC-0001", ev.id)
    assert retrieved.id == ev.id
    assert retrieved.description == ev.description


def test_create_and_get_assumption(service: EvidenceService):
    asm = service.create_assumption(
        decision_id="DEC-0001",
        category=EvidenceCategory.SUPPLIER,
        statement="Lead time will remain 7 days without delay",
        assumed_value=7,
        rationale="Contract terms",
        source="policy_config",
        action_id="ACT-0001",
    )
    assert asm.id.startswith("ASM-")
    assert asm.decision_id == "DEC-0001"
    assert asm.statement == "Lead time will remain 7 days without delay"

    retrieved = service.get_assumption("DEC-0001", asm.id)
    assert retrieved.id == asm.id
    assert retrieved.category == EvidenceCategory.SUPPLIER


def test_create_evidence_decision_not_found(service: EvidenceService):
    with pytest.raises(DecisionNotFoundError):
        service.create_evidence(
            decision_id="DEC-9999",
            evidence_type=EvidenceType.FACT,
            category=EvidenceCategory.INVENTORY,
            description="Test",
        )


def test_create_evidence_action_not_found(service: EvidenceService):
    with pytest.raises(CandidateActionNotFoundError):
        service.create_evidence(
            decision_id="DEC-0001",
            evidence_type=EvidenceType.FACT,
            category=EvidenceCategory.INVENTORY,
            description="Test",
            action_id="ACT-9999",
        )


def test_create_evidence_cross_decision_action_rejected(service: EvidenceService):
    # ACT-0002 belongs to DEC-0002, cannot attach to DEC-0001
    with pytest.raises(CrossDecisionIsolationError):
        service.create_evidence(
            decision_id="DEC-0001",
            evidence_type=EvidenceType.FACT,
            category=EvidenceCategory.INVENTORY,
            description="Test",
            action_id="ACT-0002",
        )


def test_create_evidence_version_not_found(service: EvidenceService):
    with pytest.raises(DecisionVersionNotFoundError):
        service.create_evidence(
            decision_id="DEC-0001",
            evidence_type=EvidenceType.FACT,
            category=EvidenceCategory.INVENTORY,
            description="Test",
            version_id="VER-9999",
        )


def test_record_evidence_payload_cross_decision_rejected(service: EvidenceService):
    ev = DecisionEvidence(
        id="EVD-9999",
        decision_id="DEC-0002",  # Mismatch with target DEC-0001
        evidence_type=EvidenceType.FACT,
        category=EvidenceCategory.INVENTORY,
        description="Cross decision test",
    )
    with pytest.raises(CrossDecisionIsolationError):
        service.record_evidence_item("DEC-0001", ev)


def test_cross_decision_evidence_retrieval_isolation(service: EvidenceService):
    ev1 = service.create_evidence(
        decision_id="DEC-0001",
        evidence_type=EvidenceType.FACT,
        category=EvidenceCategory.INVENTORY,
        description="Dec 1 evidence",
    )

    # Calling get_evidence for DEC-0002 should raise EvidenceNotFoundError
    with pytest.raises(EvidenceNotFoundError):
        service.get_evidence("DEC-0002", ev1.id)


def test_compile_decision_evidence_sheet(service: EvidenceService):
    sheet = service.compile_decision_evidence("DEC-0001", record_to_repository=True)

    assert sheet.id.startswith("EVS-")
    assert sheet.decision_id == "DEC-0001"
    assert sheet.product_id == "prod-001"
    assert sheet.warehouse_id == "wh-001"

    # Verify observable facts are present
    fact_sources = {item.source for item in sheet.items if item.source}
    assert "inventory:prod-001@wh-001" in fact_sources
    assert "warehouse:wh-001" in fact_sources
    assert "product:prod-001" in fact_sources

    # Verify calculations are present
    calc_sources = {item.source for item in sheet.items if item.evidence_type == EvidenceType.CALCULATION}
    assert "calculation:replenishment" in calc_sources
    assert "calculation:stockout_risk" in calc_sources

    # Invariant: deterministic exposure is strictly is_probability: False
    risk_item = next(item for item in sheet.items if item.source == "calculation:stockout_risk")
    assert risk_item.is_probability is False
    assert risk_item.unit == "ratio"

    # Verify explicit assumptions are separated
    assert len(sheet.assumptions) >= 3
    asm_categories = {asm.category for asm in sheet.assumptions}
    assert EvidenceCategory.DEMAND in asm_categories
    assert EvidenceCategory.SUPPLIER in asm_categories
    assert EvidenceCategory.STOCKOUT_RISK in asm_categories

    # Verify summary
    assert sheet.summary.total_items == len(sheet.items)
    assert sheet.summary.total_facts >= 3
    assert sheet.summary.total_calculations >= 2
    assert sheet.summary.total_assumptions >= 3


def test_get_evidence_sheet_auto_compile_and_cache(service: EvidenceService):
    # First call: auto compiles
    sheet1 = service.get_evidence_sheet("DEC-0001", auto_compile=True)
    assert sheet1 is not None

    # Second call without recompute: returns cached sheet
    sheet2 = service.get_evidence_sheet("DEC-0001", auto_compile=False, recompute=False)
    assert sheet2.id == sheet1.id

    # Third call with recompute: generates fresh sheet
    sheet3 = service.get_evidence_sheet("DEC-0001", recompute=True)
    assert sheet3.id != sheet1.id


def test_get_evidence_sheet_without_auto_compile_raises_when_empty(service: EvidenceService):
    with pytest.raises(EvidenceNotFoundError):
        service.get_evidence_sheet("DEC-0002", auto_compile=False)
