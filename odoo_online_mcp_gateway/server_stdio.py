# -*- coding: utf-8 -*-
import json
import logging
import os
import sys
import time
from typing import Optional

from .logging_config import get_logger

logger = get_logger(__name__)

_FRAMING_ENV_VARS = ("MCP_STDIO_FRAMING", "GATEWAY_STDIO_FRAMING")


def _read_exact(stream, nbytes: int) -> bytes:
    data = b""
    while len(data) < nbytes:
        chunk = stream.read(nbytes - len(data))
        if not chunk:
            break
        data += chunk
    return data


def _read_message(stdin_buffer) -> Optional[bytes]:
    first = stdin_buffer.readline()
    if not first:
        # EOF (stdin closed)
        return b""

    # Newline-delimited JSON fallback
    if first.lstrip().startswith(b"{"):
        return first

    headers = {}
    line = first
    while line:
        sline = line.decode("utf-8", errors="replace").strip()
        if not sline:
            break
        if ":" in sline:
            k, v = sline.split(":", 1)
            headers[k.strip().lower()] = v.strip()
        line = stdin_buffer.readline()

    length = headers.get("content-length")
    if not length:
        return None
    try:
        length = int(length)
    except ValueError:
        return None
    if length <= 0:
        return None

    return _read_exact(stdin_buffer, length)


def _write_message(stdout_buffer, payload_obj):
    """
    Write a single MCP response message.

    MCP stdio transport (2025-06-18) expects newline-delimited JSON (one JSON object per line).
    For backward compatibility, we also support legacy LSP-style Content-Length framing via
    MCP_STDIO_FRAMING=content-length (or GATEWAY_STDIO_FRAMING=content-length).
    """
    framing = ""
    for k in _FRAMING_ENV_VARS:
        framing = (os.environ.get(k) or "").strip().lower()
        if framing:
            break

    # Default: newline-delimited JSON per MCP spec.
    if framing in ("", "ndjson", "newline", "newline-delimited", "jsonl"):
        data = json.dumps(payload_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        stdout_buffer.write(data + b"\n")
        stdout_buffer.flush()
        return

    # Legacy: LSP-style framing
    if framing in ("content-length", "lsp", "headers"):
        data = json.dumps(payload_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        header = ("Content-Length: %d\r\n\r\n" % len(data)).encode("ascii")
        stdout_buffer.write(header)
        stdout_buffer.write(data)
        stdout_buffer.flush()
        return

    # Unknown setting: fall back to spec-compliant NDJSON.
    logger.warning("Unknown stdio framing %r; defaulting to NDJSON", framing)
    data = json.dumps(payload_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    stdout_buffer.write(data + b"\n")
    stdout_buffer.flush()


def run_stdio(handler):
    """Run MCP stdio server using newline-delimited JSON responses (MCP spec)."""
    stdin_buffer = sys.stdin.buffer
    stdout_buffer = sys.stdout.buffer

    bearer = os.environ.get("GATEWAY_TOKEN") or os.environ.get("ODOO_MCP_TOKEN") or ""
    if not bearer:
        logger.warning("Missing GATEWAY_TOKEN env var (bearer token for gateway authentication)")
        logger.info("Tip: set GATEWAY_TOKEN to one of the tokens configured in GATEWAY_CONFIG / GATEWAY_TOKENS")

    logger.debug("MCP stdio gateway started")

    while True:
        raw = _read_message(stdin_buffer)
        if raw == b"":
            logger.info("stdin closed; exiting")
            return
        if raw is None:
            time.sleep(0.01)
            continue
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            logger.debug("Failed to parse JSON: %s", exc)
            payload = {"jsonrpc": "2.0", "id": None, "error": {"code": -32602, "message": "Invalid params"}}

        resp, _status = handler.handle(payload=payload, bearer_token=bearer, raw_bytes=raw)
        _write_message(stdout_buffer, resp)
