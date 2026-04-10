import time
import uuid

import structlog
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Per-request responsibilities:
      1. Generate a request ID and bind it into structlog context vars so every
         log line emitted anywhere during the request carries it automatically.
      2. Log the incoming request (DEBUG — omitted in production).
      3. Log the completed response at a level that reflects the outcome:
           2xx/3xx → INFO, 4xx → WARNING, 5xx → ERROR.
      4. Catch any exception that escapes all exception handlers (i.e. a genuine
         programming error), log it with a full traceback, and return a clean
         500 — the client never sees a raw Python exception.
      5. Attach X-Request-ID to the response header for client-side correlation.
      6. Clear context vars after the request so they never bleed into the next.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        logger.debug(
            "request_started",
            client=request.client.host if request.client else None,
            query=str(request.query_params) or None,
        )

        start = time.perf_counter()
        status_code = 500
        response: Response | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # An exception here means no registered handler caught it.
            # Log with full traceback and return a safe response.
            logger.exception("unhandled_exception")
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
            status_code = 500
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)

            log = (
                logger.error if status_code >= 500
                else logger.warning if status_code >= 400
                else logger.info
            )
            log(
                "request_finished",
                status_code=status_code,
                duration_ms=duration_ms,
            )

            if response is not None:
                response.headers["X-Request-ID"] = request_id

            structlog.contextvars.clear_contextvars()

        return response  # type: ignore[return-value]
