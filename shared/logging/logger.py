"""
Structured logging via structlog.

Every service uses this logger. Output format:
- Development: colored, human-readable key=value
- Production (APEX_ENV=production): JSON lines for log aggregation

Usage:
    from shared.logging.logger import get_logger
    logger = get_logger(__name__)
    logger.info("event_detected", figi="BBG000B9XRY4", event_type="MA_ACQUISITION_TARGET")
"""

from __future__ import annotations

import logging
import os
import sys

import structlog


def _configure_structlog() -> None:
    """
    Configure structlog once at import time.

    In production: JSON output for log aggregation (ELK, CloudWatch, etc.)
    In development: colored, human-readable key=value output.
    """
    is_production = os.environ.get("APEX_ENV") == "production"
    service_name = os.environ.get("APEX_SERVICE", "unknown")

    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if is_production:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ],
            ),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog formatting
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(
        logging.INFO if is_production else logging.DEBUG
    )

    # Inject service name into all log entries
    structlog.contextvars.bind_contextvars(service=service_name)


# Configure on import
_configure_structlog()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger bound to the given module name.

    Args:
        name: Module name (typically __name__)

    Returns:
        Bound structlog logger

    Usage:
        logger = get_logger(__name__)
        logger.info("processing_event", event_id="abc-123", confidence=0.85)
    """
    return structlog.get_logger(name)
