"""
Observability and reliability infrastructure for EDOS.

Provides:
- Structured logging with operational context (decision_id, operation, duration_ms, outcome, error_code).
- Request timing and correlation middleware (X-Request-ID, X-Response-Time-Ms).
- Consistent, backward-compatible API exception handlers.
- Safe log sanitization preventing sensitive data leakage.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Mapping

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

SETTINGS = get_settings()

SENSITIVE_KEY_PATTERNS = [
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
]

DECISION_ID_REGEX = re.compile(r"/api/decisions?/([^/?]+)")


class StructuredLogFormatter(logging.Formatter):
    """
    Outputs human-readable structured logs with contextual fields.
    Formats logs consistently for development and production log collectors.
    """

    def format(self, record: logging.LogRecord) -> str:
        base_message = super().format(record)
        context_parts: list[str] = []

        if hasattr(record, "operation") and record.operation:
            context_parts.append(f"op={record.operation}")
        if hasattr(record, "decision_id") and record.decision_id:
            context_parts.append(f"decision_id={record.decision_id}")
        if hasattr(record, "outcome") and record.outcome:
            context_parts.append(f"outcome={record.outcome}")
        if hasattr(record, "duration_ms") and record.duration_ms is not None:
            context_parts.append(f"duration={record.duration_ms:.2f}ms")
        if hasattr(record, "error_code") and record.error_code:
            context_parts.append(f"error_code={record.error_code}")
        if hasattr(record, "error_category") and record.error_category:
            context_parts.append(f"category={record.error_category}")

        if context_parts:
            return f"{base_message} [{' '.join(context_parts)}]"
        return base_message


def sanitize_data(data: Any, max_depth: int = 3) -> Any:
    """
    Recursively strips sensitive keys and limits massive payloads.
    """
    if max_depth <= 0:
        return "[TRUNCATED_DEPTH]"
    if isinstance(data, Mapping):
        sanitized = {}
        for k, v in data.items():
            k_str = str(k)
            if any(pat.search(k_str) for pat in SENSITIVE_KEY_PATTERNS):
                sanitized[k_str] = "[REDACTED]"
            else:
                sanitized[k_str] = sanitize_data(v, max_depth - 1)
        return sanitized
    if isinstance(data, (list, tuple)):
        if len(data) > 50:
            return [sanitize_data(item, max_depth - 1) for item in data[:50]] + [
                f"... {len(data) - 50} more items"
            ]
        return [sanitize_data(item, max_depth - 1) for item in data]
    return data


def setup_observability_logging() -> logging.Logger:
    """
    Initializes and configures the root EDOS logger.
    """
    logger = logging.getLogger("edos")
    level_name = getattr(SETTINGS, "log_level", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = StructuredLogFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    return logger


LOGGER = setup_observability_logging()


def get_logger(name: str = "edos") -> logging.Logger:
    """Returns a namespaced EDOS logger."""
    return logging.getLogger(name)


def log_decision_operation(
    operation: str,
    decision_id: str | None = None,
    outcome: str = "SUCCESS",
    duration_ms: float = 0.0,
    error_code: str | None = None,
    error_category: str | None = None,
    message: str | None = None,
    details: dict | None = None,
    level: int | None = None,
) -> None:
    """
    Emits a structured operational log entry for decision operations.
    """
    log_level = level
    if log_level is None:
        if outcome == "SUCCESS":
            log_level = logging.INFO
        elif outcome in ("INCOMPLETE", "WARNING"):
            log_level = logging.WARNING
        else:
            log_level = logging.ERROR

    msg = message or f"Operation '{operation}' completed with outcome '{outcome}'"
    extra = {
        "operation": operation,
        "decision_id": decision_id,
        "outcome": outcome,
        "duration_ms": duration_ms,
        "error_code": error_code,
        "error_category": error_category,
    }
    if details:
        clean_details = sanitize_data(details)
        msg = f"{msg} | details={json.dumps(clean_details, default=str)}"

    LOGGER.log(log_level, msg, extra=extra)


def map_status_to_error_code(status_code: int, detail: Any) -> tuple[str, str]:
    """
    Maps HTTP status codes and detail text to stable error codes and categories.
    """
    detail_str = str(detail).lower() if detail else ""

    if status_code == status.HTTP_400_BAD_REQUEST:
        return "INVALID_REQUEST", "INVALID_INPUT"

    if status_code == status.HTTP_404_NOT_FOUND:
        if "decision" in detail_str:
            return "DECISION_NOT_FOUND", "NOT_FOUND"
        if "replay" in detail_str:
            return "REPLAY_RECORD_NOT_FOUND", "REPLAY"
        if "scenario" in detail_str:
            return "SCENARIO_RECORD_NOT_FOUND", "SCENARIO"
        if "provenance" in detail_str:
            return "PROVENANCE_NOT_FOUND", "PROVENANCE"
        if "evidence" in detail_str or "assumption" in detail_str:
            return "EVIDENCE_NOT_FOUND", "EVIDENCE"
        if "validation" in detail_str:
            return "VALIDATION_NOT_FOUND", "VALIDATION"
        if "action" in detail_str:
            return "ACTION_NOT_FOUND", "NOT_FOUND"
        return "RESOURCE_NOT_FOUND", "NOT_FOUND"

    if status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        if "lifecycle" in detail_str or "transition" in detail_str:
            return "INVALID_LIFECYCLE_TRANSITION", "LIFECYCLE"
        if "isolation" in detail_str or "cross-decision" in detail_str:
            return "CROSS_DECISION_ISOLATION_VIOLATION", "ISOLATION"
        if "insufficient" in detail_str or "context" in detail_str:
            return "INSUFFICIENT_CONTEXT", "CONTEXT"
        if "scenario" in detail_str:
            return "INVALID_SCENARIO_PARAMETERS", "SCENARIO"
        if "question" in detail_str:
            return "INVALID_QUESTION", "QA"
        return "VALIDATION_ERROR", "VALIDATION"

    if status_code == status.HTTP_502_BAD_GATEWAY:
        if "ungrounded" in detail_str or "citation" in detail_str:
            return "LLM_UNGROUNDED_EVIDENCE", "AI_PROVIDER"
        if "malformed" in detail_str or "invalid model output" in detail_str:
            return "LLM_MALFORMED_OUTPUT", "AI_PROVIDER"
        return "LLM_BAD_GATEWAY", "AI_PROVIDER"

    if status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
        if "timeout" in detail_str:
            return "LLM_TIMEOUT", "AI_PROVIDER"
        if (
            "offline" in detail_str
            or "connection" in detail_str
            or "connect" in detail_str
            or "unavailable" in detail_str
            or "ollama" in detail_str
        ):
            return "LLM_RUNTIME_UNAVAILABLE", "AI_PROVIDER"
        return "SERVICE_UNAVAILABLE", "SERVICE"

    if status_code >= 500:
        return "INTERNAL_SERVER_ERROR", "INTERNAL_ERROR"

    return "OPERATION_FAILED", "GENERIC"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware that instruments every incoming request:
    - Injects unique X-Request-ID
    - Measures duration in ms and sets X-Response-Time-Ms
    - Logs request metrics without leaking sensitive information
    """

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        req_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id

        path = request.url.path
        method = request.method

        # Extract decision ID from path if present
        match = DECISION_ID_REGEX.search(path)
        decision_id = match.group(1) if match else None

        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log_decision_operation(
                operation=f"{method} {path}",
                decision_id=decision_id,
                outcome="FAILED",
                duration_ms=duration_ms,
                error_code="UNHANDLED_EXCEPTION",
                error_category="INTERNAL_ERROR",
                message=f"Unhandled request error: {str(exc)}",
                level=logging.ERROR,
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Attach tracing headers if response object exists
            if "response" in locals() and response is not None:
                response.headers["X-Request-ID"] = req_id
                response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

            # Skip spammy health checks in operational logs
            if path != "/health" and path != "/api/health":
                outcome = (
                    "SUCCESS"
                    if status_code < 400
                    else "CLIENT_ERROR"
                    if status_code < 500
                    else "SERVER_ERROR"
                )
                level = (
                    logging.INFO
                    if status_code < 400
                    else logging.WARNING
                    if status_code < 500
                    else logging.ERROR
                )
                LOGGER.log(
                    level,
                    f"{method} {path} -> HTTP {status_code}",
                    extra={
                        "operation": f"{method} {path}",
                        "decision_id": decision_id,
                        "outcome": outcome,
                        "duration_ms": duration_ms,
                        "error_code": None if status_code < 400 else f"HTTP_{status_code}",
                        "error_category": "HTTP",
                    },
                )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Standardized HTTPException handler that keeps 'detail' compatible
    while attaching structured 'error_code' and 'category'.
    """
    error_code, category = map_status_to_error_code(exc.status_code, exc.detail)

    match = DECISION_ID_REGEX.search(request.url.path)
    decision_id = match.group(1) if match else None

    # Log client/server error with structured context
    level = logging.WARNING if exc.status_code < 500 else logging.ERROR
    LOGGER.log(
        level,
        f"API Error: {exc.detail}",
        extra={
            "operation": f"{request.method} {request.url.path}",
            "decision_id": decision_id,
            "outcome": "FAILED",
            "duration_ms": 0.0,
            "error_code": error_code,
            "error_category": category,
        },
    )

    content = {
        "detail": exc.detail,
        "error_code": error_code,
        "category": category,
        "message": str(exc.detail) if isinstance(exc.detail, str) else "Request error",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, "headers", None),
    )


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Standardized RequestValidationError handler.
    Preserves exc.errors() in 'detail' for test compatibility while providing error_code and category.
    """
    match = DECISION_ID_REGEX.search(request.url.path)
    decision_id = match.group(1) if match else None

    LOGGER.warning(
        f"Validation Error on {request.method} {request.url.path}: {len(exc.errors())} error(s)",
        extra={
            "operation": f"{request.method} {request.url.path}",
            "decision_id": decision_id,
            "outcome": "VALIDATION_FAILED",
            "duration_ms": 0.0,
            "error_code": "VALIDATION_ERROR",
            "error_category": "VALIDATION",
        },
    )

    content = {
        "detail": exc.errors(),
        "error_code": "VALIDATION_ERROR",
        "category": "VALIDATION",
        "message": "Input validation failed. Please check the supplied parameters.",
    }
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=content,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catches unexpected internal exceptions.
    Logs complete traceback server-side without leaking internals to the client.
    """
    match = DECISION_ID_REGEX.search(request.url.path)
    decision_id = match.group(1) if match else None

    LOGGER.error(
        f"Unexpected internal server error on {request.method} {request.url.path}: {str(exc)}",
        exc_info=True,
        extra={
            "operation": f"{request.method} {request.url.path}",
            "decision_id": decision_id,
            "outcome": "INTERNAL_ERROR",
            "duration_ms": 0.0,
            "error_code": "INTERNAL_SERVER_ERROR",
            "error_category": "INTERNAL_ERROR",
        },
    )

    content = {
        "detail": "An internal operational error occurred while processing the decision.",
        "error_code": "INTERNAL_SERVER_ERROR",
        "category": "INTERNAL_ERROR",
        "message": "An internal operational error occurred. The technical team has been alerted.",
    }
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
    )
