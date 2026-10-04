from fastapi import FastAPI
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


# Canonical API router prefix
app.include_router(inventory_router, prefix="/api/inventory", tags=["inventory"])

# Direct router alias for /inventory
app.include_router(inventory_router, prefix="/inventory", tags=["inventory"], include_in_schema=False)
