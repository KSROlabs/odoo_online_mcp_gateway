# -*- coding: utf-8 -*-
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


PHASE1_MODELS = [
    "stock.picking",
    "sale.order",
    "res.partner",
    "account.move",
    "crm.lead",
]


@dataclass(frozen=True)
class Limits:
    max_payload_kb: int = 512
    rate_limit_per_minute: int = 120


@dataclass(frozen=True)
class Audit:
    enabled: bool = True
    log_path: Optional[str] = None
    log_payloads: bool = False


@dataclass(frozen=True)
class Settings:
    odoo_base_url: str
    odoo_db: str
    odoo_login: str
    odoo_password: str
    tokens: List[Dict[str, Any]]
    limits: Limits
    audit: Audit
    hide_internal_errors: bool = True


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("1", "true", "yes", "y", "on"):
            return True
        if s in ("0", "false", "no", "n", "off", ""):
            return False
    return default


def _load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_token_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a single token entry with environment variable resolution and defaults.

    Args:
        entry: Token entry dict with optional token/token_env and policy

    Returns:
        Normalized entry dict

    Raises:
        RuntimeError: If token is missing
    """
    entry = dict(entry)  # Copy to avoid mutations

    # Resolve token from literal or environment variable
    token = entry.get("token")
    token_env = entry.get("token_env")
    if not token and token_env:
        token = _env(str(token_env))
    if not token:
        raise RuntimeError("Token entry is missing 'token' and/or 'token_env'.")
    entry["token"] = token

    # Apply policy defaults
    policy = entry.get("policy") or {}
    if not isinstance(policy, dict):
        policy = {}
    if not policy.get("allow_models"):
        policy["allow_models"] = PHASE1_MODELS
    if not policy.get("allow_ops"):
        policy["allow_ops"] = ["read", "aggregate"]
    entry["policy"] = policy

    return entry


def _load_tokens_from_sources(
    tokens_cfg: Optional[List[Dict[str, Any]]] = None,
    env_token_string: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Load tokens from config file and/or environment variables.

    Sources (in priority order):
    1. tokens_cfg from GATEWAY_CONFIG (with token_env lookup)
    2. GATEWAY_TOKENS env var (comma-separated)

    Args:
        tokens_cfg: Token list from config file
        env_token_string: GATEWAY_TOKENS env var value

    Returns:
        List of normalized token entries

    Raises:
        RuntimeError: If no valid tokens found
    """
    out: List[Dict[str, Any]] = []

    # Source 1: Config file
    if tokens_cfg:
        for entry in tokens_cfg or []:
            if not isinstance(entry, dict):
                continue
            out.append(_normalize_token_entry(entry))

    # Source 2: Environment variable
    if env_token_string:
        tokens = [t.strip() for t in env_token_string.split(",") if t.strip()]
        for idx, tok in enumerate(tokens, start=1):
            out.append(_normalize_token_entry({
                "name": "env-token-%d" % idx,
                "token": tok,
            }))

    if not out:
        raise RuntimeError("No tokens configured. Set GATEWAY_TOKENS or GATEWAY_CONFIG.")

    return out


def load_settings() -> Settings:
    """
    Load gateway configuration from environment and/or config file.

    Environment variables (required):
    - ODOO_BASE_URL: Odoo instance URL
    - ODOO_DB: Database name
    - ODOO_LOGIN: User login
    - ODOO_PASSWORD: User password or API key

    Environment variables (optional):
    - GATEWAY_CONFIG: Path to JSON config file
    - GATEWAY_TOKENS: Comma-separated bearer tokens (if no config file)
    - GATEWAY_RATE_LIMIT_PER_MINUTE: Rate limit (default: 120)
    - GATEWAY_MAX_PAYLOAD_KB: Max request size (default: 512)
    - GATEWAY_AUDIT_ENABLED: Enable audit logging (default: true)
    - GATEWAY_AUDIT_LOG_PATH: Audit log file path
    - GATEWAY_AUDIT_LOG_PAYLOADS: Log full payloads (default: false)
    - GATEWAY_HIDE_INTERNAL_ERRORS: Hide internal exceptions from clients (default: true)

    Returns:
        Settings object

    Raises:
        RuntimeError: If required environment variables are missing
    """
    # Optional hardening: lock config path (useful for vendor-shipped Docker images).
    # When enabled, the gateway always loads a JSON config file from a fixed path and
    # ignores any env-provided config path or GATEWAY_TOKENS.
    lock_cfg = _parse_bool(_env("GATEWAY_LOCK_CONFIG", ""), default=False)
    if lock_cfg:
        cfg_path = _env("GATEWAY_LOCK_CONFIG_PATH", "/app/config.json")
    else:
        cfg_path = _env("GATEWAY_CONFIG")

    if cfg_path:
        cfg = _load_json_file(cfg_path)
        tokens = _load_tokens_from_sources(tokens_cfg=cfg.get("tokens") or [])
        limits_cfg = cfg.get("limits") or {}
        audit_cfg = cfg.get("audit") or {}
        security_cfg = cfg.get("security") or {}
    else:
        cfg = {}
        env_tokens = _env("GATEWAY_TOKENS", "")
        tokens = _load_tokens_from_sources(env_token_string=env_tokens)
        limits_cfg = {}
        audit_cfg = {}
        security_cfg = {}

    odoo_base_url = _env("ODOO_BASE_URL")
    odoo_db = _env("ODOO_DB")
    odoo_login = _env("ODOO_LOGIN")
    odoo_password = _env("ODOO_PASSWORD")

    missing = [k for k, v in [
        ("ODOO_BASE_URL", odoo_base_url),
        ("ODOO_DB", odoo_db),
        ("ODOO_LOGIN", odoo_login),
        ("ODOO_PASSWORD", odoo_password),
    ] if not v]
    if missing:
        raise RuntimeError("Missing required environment variables: %s" % ", ".join(missing))

    limits = Limits(
        max_payload_kb=int(limits_cfg.get("max_payload_kb", _env("GATEWAY_MAX_PAYLOAD_KB", "512"))),
        rate_limit_per_minute=int(limits_cfg.get("rate_limit_per_minute", _env("GATEWAY_RATE_LIMIT_PER_MINUTE", "120"))),
    )

    audit = Audit(
        enabled=_parse_bool(audit_cfg.get("enabled"), default=_parse_bool(_env("GATEWAY_AUDIT_ENABLED", "1"), default=True)),
        log_path=audit_cfg.get("log_path", _env("GATEWAY_AUDIT_LOG_PATH")),
        log_payloads=_parse_bool(audit_cfg.get("log_payloads"), default=_parse_bool(_env("GATEWAY_AUDIT_LOG_PAYLOADS", "0"), default=False)),
    )

    return Settings(
        odoo_base_url=odoo_base_url.rstrip("/"),
        odoo_db=odoo_db,
        odoo_login=odoo_login,
        odoo_password=odoo_password,
        tokens=tokens,
        limits=limits,
        audit=audit,
        hide_internal_errors=_parse_bool(
            security_cfg.get("hide_internal_errors"),
            default=_parse_bool(_env("GATEWAY_HIDE_INTERNAL_ERRORS", "1"), default=True),
        ),
    )
