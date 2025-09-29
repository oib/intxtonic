from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


def standard_error(status: int, code: str, message: str, details: dict | None = None):
    return {"error": {"status": status, "code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        payload = standard_error(exc.status_code, "http_error", exc.detail if exc.detail else "HTTP error")
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        details = {"errors": exc.errors()}
        payload = standard_error(422, "validation_error", "Validation failed", details)
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        payload = standard_error(500, "server_error", "Internal server error")
        return JSONResponse(status_code=500, content=payload)
