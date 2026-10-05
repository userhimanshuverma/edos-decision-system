from fastapi import FastAPI
from app.api.demand import router as demand_router
from app.api.inventory import router as inventory_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.service_name,
    }


# Canonical API router prefixes
app.include_router(inventory_router, prefix="/api/inventory", tags=["inventory"])
app.include_router(demand_router, prefix="/api/demand", tags=["demand"])

# Direct router aliases
app.include_router(inventory_router, prefix="/inventory", tags=["inventory"], include_in_schema=False)
app.include_router(demand_router, prefix="/demand", tags=["demand"], include_in_schema=False)

