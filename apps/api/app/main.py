from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.context import router as context_router
from app.api.demand import router as demand_router
from app.api.inventory import router as inventory_router
from app.api.supplier import router as supplier_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(supplier_router, prefix="/api/suppliers", tags=["suppliers"])
app.include_router(context_router, prefix="/api/context", tags=["context"])

# Direct router aliases
app.include_router(inventory_router, prefix="/inventory", tags=["inventory"], include_in_schema=False)
app.include_router(demand_router, prefix="/demand", tags=["demand"], include_in_schema=False)
app.include_router(supplier_router, prefix="/suppliers", tags=["suppliers"], include_in_schema=False)
app.include_router(supplier_router, prefix="/api/supplier", tags=["suppliers"], include_in_schema=False)
app.include_router(supplier_router, prefix="/supplier", tags=["suppliers"], include_in_schema=False)
app.include_router(context_router, prefix="/context", tags=["context"], include_in_schema=False)

