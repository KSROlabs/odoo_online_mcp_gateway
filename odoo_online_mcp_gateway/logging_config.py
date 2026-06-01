# -*- coding: utf-8 -*-
"""
Structured logging setup for the MCP gateway.

Usage:
    from odoo_online_mcp_gateway.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Connected to Odoo", extra={"url": base_url})
"""
import logging
import sys
import os
from typing import Optional

from .constants import DEFAULT_LOG_FORMAT


_configured = False


def setup_logging(debug: bool = False, log_file: Optional[str] = None) -> None:
    """
    Initialize structured logging for the gateway.

    Args:
        debug: If True, log at DEBUG level; otherwise INFO
        log_file: Optional file path for file logging (in addition to stderr)
    """
    global _configured
    if _configured:
        return

    # Determine log level
    env_debug = os.environ.get("GATEWAY_DEBUG", "").lower() in ("1", "true", "yes")
    level = logging.DEBUG if (debug or env_debug) else logging.INFO

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Clear any existing handlers
    root.handlers.clear()

    # Stderr handler (always on)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(level)
    formatter = logging.Formatter(DEFAULT_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    # File handler (optional)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as exc:
            root.warning("Could not open log file %s: %s", log_file, exc)

    # Suppress noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("xmlrpc").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Usually __name__

    Returns:
        Logger instance
    """
    if not _configured:
        setup_logging()
    return logging.getLogger(name)
