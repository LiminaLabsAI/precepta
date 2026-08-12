"""One standard error envelope for the whole API (Phase 15).

Every error response is `{"error": {"message", "type", "code"?}}` so integrators
can branch on a stable shape. `type` is a coarse machine class; `code` is an
optional finer-grained slug.
"""
from __future__ import annotations

from fastapi.responses import JSONResponse


def error_json(status: int, type_: str, message: str,
               code: str | None = None) -> JSONResponse:
    body: dict = {"error": {"message": message, "type": type_}}
    if code:
        body["error"]["code"] = code
    return JSONResponse(body, status_code=status)


# Common shorthands
def unauthorized(message: str = "authentication required") -> JSONResponse:
    return error_json(401, "unauthenticated", message)


def forbidden(message: str = "forbidden", code: str | None = None) -> JSONResponse:
    return error_json(403, "forbidden", message, code)


def not_found(message: str = "not found") -> JSONResponse:
    return error_json(404, "not_found", message)


def invalid_request(message: str, code: str | None = None) -> JSONResponse:
    return error_json(400, "invalid_request_error", message, code)
