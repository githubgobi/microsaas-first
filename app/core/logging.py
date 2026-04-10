"""
Logging configuration.

Bridges Python's stdlib `logging` (used by SQLAlchemy, uvicorn, httpx, etc.)
into structlog's processor chain so all output is uniform JSON.

Call configure_logging() once at application startup, before any loggers are used.
"""
import logging
import sys

import structlog


def configure_logging(debug: bool = False) -> None:
    log_level = logging.DEBUG if debug else logging.INFO

    # Processors shared by both structlog and stdlib-originated records
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,   # injects per-request bound fields
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # structlog: use stdlib as the underlying logger so the two channels share one handler
    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )

    # ProcessorFormatter: final rendering step for both structlog and stdlib records
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,   # renders traceback to "exception" string
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,        # applied to stdlib records before merging
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Silence libraries that are too chatty at INFO
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    # We write request logs ourselves — disable uvicorn's duplicate access log
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
