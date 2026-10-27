from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.api.context import router as context_router
from app.api.decision import router as decision_router
from app.api.demand import router as demand_router
from app.api.inventory import router as inventory_router
from app.api.supplier import router as supplier_router
from app.config import get_settings
from app.observability import (
    ObservabilityMiddleware,
    http_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
)

# Day 29: Observability & request timing middleware
app.add_middleware(ObservabilityMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Day 29: Standardized exception handlers preserving backwards compatibility
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health")
@app.get("/api/health")
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
app.include_router(decision_router, prefix="/api/decisions", tags=["decisions"])

# Direct router aliases
app.include_router(inventory_router, prefix="/inventory", tags=["inventory"], include_in_schema=False)
app.include_router(demand_router, prefix="/demand", tags=["demand"], include_in_schema=False)
app.include_router(supplier_router, prefix="/suppliers", tags=["suppliers"], include_in_schema=False)
app.include_router(supplier_router, prefix="/api/supplier", tags=["suppliers"], include_in_schema=False)
app.include_router(supplier_router, prefix="/supplier", tags=["suppliers"], include_in_schema=False)
app.include_router(context_router, prefix="/context", tags=["context"], include_in_schema=False)
app.include_router(decision_router, prefix="/decisions", tags=["decisions"], include_in_schema=False)
app.include_router(decision_router, prefix="/api/decision", tags=["decisions"], include_in_schema=False)
app.include_router(decision_router, prefix="/decision", tags=["decisions"], include_in_schema=False)


