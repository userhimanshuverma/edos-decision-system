from __future__ import annotations

import datetime as dt
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.schemas import DemandResponse, DemandTrendResponse
from app.repositories.demand_repository import DemandRepository

router = APIRouter()


@lru_cache
def get_demand_repository() -> DemandRepository:
    """Dependency provider returning the singleton DemandRepository instance."""
    return DemandRepository()


@router.get(
    "",
    response_model=list[DemandResponse],
    summary="List all historical demand records",
    description="Retrieve all observed historical demand records, with optional filtering by product, warehouse, and date range.",
)
def list_demand(
    product_id: str | None = Query(default=None, description="Optional product ID filter"),
    warehouse_id: str | None = Query(default=None, description="Optional warehouse ID filter"),
    start_date: dt.date | None = Query(default=None, description="Optional start date (inclusive, YYYY-MM-DD)"),
    end_date: dt.date | None = Query(default=None, description="Optional end date (inclusive, YYYY-MM-DD)"),
    repo: DemandRepository = Depends(get_demand_repository),
) -> list[DemandResponse]:
    records = repo.list_all(
        product_id=product_id,
        warehouse_id=warehouse_id,
        start_date=start_date,
        end_date=end_date,
    )
    return [DemandResponse.from_domain(dem) for dem in records]


@router.get(
    "/product/{product_id}/trend",
    response_model=DemandTrendResponse,
    summary="Get historical demand trend for a product",
    description="Calculates deterministic historical demand aggregation and consumption trajectory for a product.",
)
def get_product_demand_trend(
    product_id: str,
    warehouse_id: str | None = Query(default=None, description="Optional warehouse filter"),
    start_date: dt.date | None = Query(default=None, description="Optional start date (inclusive, YYYY-MM-DD)"),
    end_date: dt.date | None = Query(default=None, description="Optional end date (inclusive, YYYY-MM-DD)"),
    repo: DemandRepository = Depends(get_demand_repository),
) -> DemandTrendResponse:
    if not repo.product_exists(product_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found",
        )
    if warehouse_id is not None and not repo.warehouse_exists(warehouse_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse '{warehouse_id}' not found",
        )

    trend_data = repo.get_product_demand_trend(
        product_id=product_id,
        warehouse_id=warehouse_id,
        start_date=start_date,
        end_date=end_date,
    )
    return DemandTrendResponse(**trend_data)


@router.get(
    "/product/{product_id}",
    response_model=list[DemandResponse],
    summary="Get historical demand by product",
    description="Retrieve historical demand records for a specific product ID across all or filtered warehouses.",
)
def get_demand_by_product(
    product_id: str,
    warehouse_id: str | None = Query(default=None, description="Optional warehouse ID filter"),
    start_date: dt.date | None = Query(default=None, description="Optional start date filter"),
    end_date: dt.date | None = Query(default=None, description="Optional end date filter"),
    repo: DemandRepository = Depends(get_demand_repository),
) -> list[DemandResponse]:
    if not repo.product_exists(product_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found",
        )
    if warehouse_id is not None:
        if not repo.warehouse_exists(warehouse_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Warehouse '{warehouse_id}' not found",
            )
        records = repo.get_by_product_and_warehouse(
            product_id=product_id,
            warehouse_id=warehouse_id,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        records = repo.get_by_product_id(
            product_id=product_id,
            start_date=start_date,
            end_date=end_date,
        )
    return [DemandResponse.from_domain(dem) for dem in records]


@router.get(
    "/warehouse/{warehouse_id}",
    response_model=list[DemandResponse],
    summary="Get historical demand by warehouse",
    description="Retrieve historical demand records located in a specific warehouse.",
)
def get_demand_by_warehouse(
    warehouse_id: str,
    product_id: str | None = Query(default=None, description="Optional product ID filter"),
    start_date: dt.date | None = Query(default=None, description="Optional start date filter"),
    end_date: dt.date | None = Query(default=None, description="Optional end date filter"),
    repo: DemandRepository = Depends(get_demand_repository),
) -> list[DemandResponse]:
    if not repo.warehouse_exists(warehouse_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse '{warehouse_id}' not found",
        )
    if product_id is not None:
        if not repo.product_exists(product_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product '{product_id}' not found",
            )
        records = repo.get_by_product_and_warehouse(
            product_id=product_id,
            warehouse_id=warehouse_id,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        records = repo.get_by_warehouse_id(
            warehouse_id=warehouse_id,
            start_date=start_date,
            end_date=end_date,
        )
    return [DemandResponse.from_domain(dem) for dem in records]


@router.get(
    "/{demand_id}",
    response_model=DemandResponse,
    summary="Get demand record by ID",
    description="Retrieve a single historical demand record by its unique ID.",
)
def get_demand_by_id(
    demand_id: str,
    repo: DemandRepository = Depends(get_demand_repository),
) -> DemandResponse:
    record = repo.get_by_id(demand_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demand record '{demand_id}' not found",
        )
    return DemandResponse.from_domain(record)
