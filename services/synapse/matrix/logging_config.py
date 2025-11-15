"""Centralized logging configuration for all BIOwerk services."""
import logging
import sys
from typing import Any, Dict

# Configure structured logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO


def setup_logging(service_name: str) -> logging.Logger:
    """
    Set up structured logging for a service.

    Args:
        service_name: Name of the service (e.g., 'mesh', 'osteon')

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(LOG_LEVEL)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler with formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(LOG_LEVEL)
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def log_request(logger: logging.Logger, msg_id: str, agent: str, endpoint: str, **kwargs: Any) -> None:
    """Log incoming request details."""
    extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"Request received: msg_id={msg_id} agent={agent} endpoint={endpoint} {extra_info}".strip())


def log_response(logger: logging.Logger, msg_id: str, agent: str, ok: bool, duration_ms: float, **kwargs: Any) -> None:
    """Log response details."""
    status = "success" if ok else "failure"
    extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"Response sent: msg_id={msg_id} agent={agent} status={status} duration_ms={duration_ms:.2f} {extra_info}".strip())


def log_error(logger: logging.Logger, msg_id: str, error: Exception, **kwargs: Any) -> None:
    """Log error details."""
    extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.error(f"Error occurred: msg_id={msg_id} error={type(error).__name__} message={str(error)} {extra_info}".strip())
