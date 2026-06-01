# -*- coding: utf-8 -*-
"""
Configuration constants and defaults.

These replace hardcoded values scattered throughout the codebase.
"""

# Odoo XML-RPC Connection
ODOO_RPC_TIMEOUT_SECONDS = 30

# HTTP Server
HTTP_DEFAULT_HOST = "127.0.0.1"
HTTP_DEFAULT_PORT = 8787

# Gateway Limits
DEFAULT_MAX_PAYLOAD_KB = 512
DEFAULT_RATE_LIMIT_PER_MINUTE = 120
DEFAULT_RATE_WINDOW_SECONDS = 60

# Search/Pagination
DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 500  # Prevent DoS via huge limit

# MCP Protocol
MCP_PROTOCOL_VERSION = "2024-11-05"

# Tool operation names (must match Odoo ORM methods)
ALLOWED_OPERATIONS = {"read", "create", "write", "unlink", "aggregate"}

# Phase 1 default models for Odoo Online
PHASE1_MODELS = [
    "stock.picking",
    "sale.order",
    "res.partner",
    "account.move",
    "crm.lead",
]

# Logging
DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
