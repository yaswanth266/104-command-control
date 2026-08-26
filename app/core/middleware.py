import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("ccc.request")

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Stamps every request/response with a correlation id (X-Request-Id) and
    turns any unhandled exception into a generic client-safe error, logging the
    full traceback server-side against the same id. HTTPException-driven
    responses (400/403/404/409/...) are untouched other than getting the header."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error [%s] %s %s", rid, request.method, request.url.path)
            return JSONResponse(
                {"detail": "Something went wrong. Please try again or contact support.", "request_id": rid},
                status_code=500,
                headers={"X-Request-Id": rid},
            )
        response.headers["X-Request-Id"] = rid
        return response
