from app.api.demand import get_demand_repository, router as demand_router
from app.api.inventory import get_inventory_repository, router as inventory_router
from app.api.schemas import (
    DailyDemandPoint,
    DemandResponse,
    DemandTrendResponse,
    InventoryResponse,
)

__all__ = [
    "DailyDemandPoint",
    "DemandResponse",
    "DemandTrendResponse",
    "InventoryResponse",
    "demand_router",
    "get_demand_repository",
    "get_inventory_repository",
    "inventory_router",
]

