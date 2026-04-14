"""
Exception handlers registered on the FastAPI application.

Coverage:
  AppException        → our own domain errors (4xx/5xx)  — WARNING/ERROR
  RequestValidationError → Pydantic / query param failures — WARNING  (422)
  HTTPException       → FastAPI / Starlette raises         — WARNING/ERROR
  Exception           → everything else                    — ERROR    (500)

All handlers:
  - Log structured context before returning
  - Return {"detail": "..."} for simple errors
  - Return {"detail": "...", "errors": [...]} for validation failures
  - Never expose internal state or tracebacks to the client
"""
import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ConflictError(AppException):
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message, status.HTTP_409_CONFLICT)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class NotFoundError(AppException):
    def __init__(self, message: str = "Not found"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class BadRequestError(AppException):
    def __init__(self, message: str = "Bad request"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class ServiceUnavailableError(AppException):
    def __init__(self, message: str = "Service unavailable"):
        super().__init__(message, status.HTTP_503_SERVICE_UNAVAILABLE)


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        log = logger.error if exc.status_code >= 500 else logger.warning
        log(
            "app_exception",
            exc_type=type(exc).__name__,
            status_code=exc.status_code,
            detail=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Normalize Pydantic's nested error format into a flat, client-friendly list
        errors = [
            {
                "field": ".".join(str(loc) for loc in err["loc"][1:]) or "body",
                "message": err["msg"],
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        logger.warning(
            "validation_error",
            error_count=len(errors),
            errors=errors,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Request validation failed",
                "errors": errors,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        log = logger.error if exc.status_code >= 500 else logger.warning
        log(
            "http_exception",
            status_code=exc.status_code,
            detail=exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Full traceback is captured by logger.exception (exc_info=True)
        logger.exception(
            "unhandled_exception",
            exc_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
