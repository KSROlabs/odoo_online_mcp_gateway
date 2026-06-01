# -*- coding: utf-8 -*-
import argparse
import json
import logging
import os
import secrets
import sys
from pathlib import Path

from .config import load_settings
from .logging_config import setup_logging
from .mcp import MCPHandler
from .odoo_xmlrpc import OdooXMLRPC
from .server_http import run_http
from .server_stdio import run_stdio

logger = logging.getLogger(__name__)


def _load_env_file(path: str, override: bool = False) -> None:
    """
    Load environment variables from a .env-style file.

    Format:
      KEY=value
      # comments supported

    By default this does not override already-set environment variables.
    """
    if not path:
        return
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    base_dir = p.parent
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key:
            continue
        # Resolve certain relative file paths relative to the env file location.
        if key in ("GATEWAY_CONFIG", "GATEWAY_AUDIT_LOG_PATH") and value and not os.path.isabs(value):
            value = str((base_dir / value).resolve())
        if not override and key in os.environ:
            continue
        os.environ[key] = value


def _write_text_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_init(out_dir: str, force: bool, token_env: str) -> int:
    """Generate a starter `.env` and `config.json` for quick production setup."""
    out = Path(out_dir).resolve()
    env_path = out / ".env"
    cfg_path = out / "config.json"

    token = secrets.token_urlsafe(32)
    env_contents = "\n".join(
        [
            "# Gateway config",
            'GATEWAY_CONFIG="config.json"',
            "",
            "# Odoo Online connection",
            'ODOO_BASE_URL="https://yourcompany.odoo.com"',
            'ODOO_DB="your_db_name"',
            'ODOO_LOGIN="integration@yourcompany.com"',
            'ODOO_PASSWORD="YOUR_PASSWORD_OR_API_KEY"',
            "",
            "# Gateway auth token (give this to your MCP client as Bearer token)",
            f'{token_env}="{token}"',
            f'GATEWAY_TOKEN="{token}"',
            "",
            "# Optional: enable debug logs",
            '# GATEWAY_DEBUG="1"',
            "",
            "# Optional: set audit log path (recommended in production)",
            'GATEWAY_AUDIT_LOG_PATH="audit.log.jsonl"',
            "",
        ]
    ) + "\n"

    cfg_obj = {
        "tokens": [
            {
                "name": "default",
                "token_env": token_env,
                "policy": {
                    "allow_models": [
                        "stock.picking",
                        "sale.order",
                        "res.partner",
                        "account.move",
                        "crm.lead",
                    ],
                    "allow_ops": ["read", "aggregate"],
                },
            }
        ],
        "limits": {"max_payload_kb": 512, "rate_limit_per_minute": 120},
        "audit": {"enabled": True, "log_path": "audit.log.jsonl", "log_payloads": False},
        "security": {"hide_internal_errors": True},
    }

    _write_text_file(env_path, env_contents, force=force)
    _write_text_file(cfg_path, (json.dumps(cfg_obj, indent=2) + "\n"), force=force)

    logger.info("Wrote %s", str(env_path))
    logger.info("Wrote %s", str(cfg_path))
    logger.info("Next: edit %s with your Odoo credentials", str(env_path))
    logger.info("Then run: odoo-online-mcp-gateway --env-file %s http", str(env_path))
    logger.info("Client token is in %s (%s)", str(env_path), token_env)
    return 0


def _run_check():
    """Run connectivity check against Odoo instance."""
    setup_logging(debug=os.getenv("GATEWAY_DEBUG", "").lower() in ("1", "true"))

    settings = load_settings()
    odoo = OdooXMLRPC(
        base_url=settings.odoo_base_url,
        db=settings.odoo_db,
        login=settings.odoo_login,
        password=settings.odoo_password,
    )

    logger.info("Odoo Online MCP Gateway - Connectivity Check")
    logger.info("Base URL: %s", settings.odoo_base_url)
    logger.info("DB: %s", settings.odoo_db)
    logger.info("Login: %s", settings.odoo_login)

    try:
        uid = odoo.authenticate()
        logger.info("Authentication: OK (uid=%s)", uid)
    except Exception as exc:
        logger.error("Authentication failed: %s", exc)
        return 1

    # Validate access to Phase 1 models (plus any extra allowlisted models in config).
    allowlisted = set()
    for t in settings.tokens:
        policy = (t.get("policy") or {})
        for m in policy.get("allow_models") or []:
            allowlisted.add(m)

    phase1 = ["stock.picking", "sale.order", "res.partner", "account.move", "crm.lead"]
    models_to_check = [m for m in phase1 if m in allowlisted] or phase1

    failures = 0
    for model in models_to_check:
        try:
            # Smallest possible calls to keep this fast and cheap.
            odoo.execute_kw(model, "fields_get", [["id"]], {"attributes": ["type", "string"]})
            rows = odoo.execute_kw(model, "search_read", [[]], {"fields": ["id"], "limit": 1})
            _ = len(rows)  # noqa: F841
            # read_group smoke (count only)
            odoo.execute_kw(model, "read_group", [[], [], []], {"lazy": False, "limit": 1})
            logger.info("[OK] %s", model)
        except Exception as exc:
            failures += 1
            logger.error("[FAIL] %s: %s", model, exc)

    if failures:
        logger.error("Result: FAIL (%d model checks failed)", failures)
        return 1
    logger.info("Result: OK")
    return 0


def main(argv=None):
    """Main CLI entrypoint for gateway modes."""
    argv = argv if argv is not None else sys.argv[1:]

    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument(
        "--env-file",
        default=os.environ.get("GATEWAY_ENV_FILE", ""),
        help="Optional .env file to load before reading configuration.",
    )
    pre_args, _ = pre.parse_known_args(argv)
    if pre_args.env_file:
        try:
            _load_env_file(pre_args.env_file, override=False)
        except FileNotFoundError:
            sys.stderr.write(f"error: --env-file not found: {pre_args.env_file}\n")
            return 2

    setup_logging(debug=os.getenv("GATEWAY_DEBUG", "").lower() in ("1", "true"))

    parser = argparse.ArgumentParser(prog="odoo-online-mcp-gateway")
    parser.add_argument(
        "--env-file",
        default=pre_args.env_file,
        help="Optional .env file to load before reading configuration.",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    http_p = sub.add_parser("http", help="Run HTTP MCP server (POST /mcp).")
    http_p.add_argument("--host", default=os.environ.get("GATEWAY_HOST", "127.0.0.1"))
    http_p.add_argument("--port", type=int, default=int(os.environ.get("GATEWAY_PORT", "8787")))

    sub.add_parser("stdio", help="Run stdio MCP server (Content-Length framing).")
    sub.add_parser("check", help="Validate Odoo connectivity + model access (smoke test).")
    init_p = sub.add_parser("init", help="Generate starter .env and config.json for production use.")
    init_p.add_argument("--out-dir", default=".", help="Directory to write files into (default: current).")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing files.")
    init_p.add_argument("--token-env", default="GATEWAY_TOKEN_1", help="Env var name to store the generated token.")

    args = parser.parse_args(argv)

    # If the user passed a different env-file after the mode (rare), load it too.
    if args.env_file and args.env_file != pre_args.env_file:
        try:
            _load_env_file(args.env_file, override=False)
        except FileNotFoundError:
            parser.error(f"--env-file not found: {args.env_file}")

    if args.mode == "init":
        return _run_init(out_dir=args.out_dir, force=bool(args.force), token_env=str(args.token_env))

    if args.mode == "check":
        return _run_check()

    settings = load_settings()
    handler = MCPHandler(settings=settings)

    if args.mode == "http":
        logger.debug("Starting HTTP mode on %s:%d", args.host, args.port)
        run_http(host=args.host, port=args.port, handler=handler)
        return 0

    if args.mode == "stdio":
        logger.debug("Starting stdio mode")
        run_stdio(handler=handler)
        return 0

    parser.error("Unknown mode")
    return 2
