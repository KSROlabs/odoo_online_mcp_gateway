# -*- coding: utf-8 -*-
import json
import logging
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

logger = logging.getLogger(__name__)


def _get_bearer(headers) -> Optional[str]:
    auth = headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    return auth.split("Bearer ", 1)[1].strip()


def run_http(host: str, port: int, handler):
    def _send_json(req, status: int, payload_obj) -> None:
        out = json.dumps(payload_obj).encode("utf-8")
        req.send_response(status)
        req.send_header("Content-Type", "application/json")
        req.send_header("Content-Length", str(len(out)))
        req.send_header("X-Content-Type-Options", "nosniff")
        req.end_headers()
        req.wfile.write(out)

    class MCPHTTPHandler(BaseHTTPRequestHandler):
        server_version = "odoo-online-mcp-gateway/0.1"

        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/healthz":
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):  # noqa: N802
            if self.path.split("?", 1)[0] != "/mcp":
                self.send_response(404)
                self.end_headers()
                return

            content_length = int(self.headers.get("Content-Length") or "0")
            max_kb = int(getattr(handler.settings.limits, "max_payload_kb", 0) or 0)
            if max_kb > 0 and content_length > max_kb * 1024:
                _send_json(
                    self,
                    413,
                    {"jsonrpc": "2.0", "id": None, "error": {"code": -32602, "message": "Invalid params", "data": "Payload too large"}},
                )
                return

            raw = self.rfile.read(content_length) if content_length else b""
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception as exc:
                logger.debug("Invalid JSON payload: %s", exc)
                _send_json(
                    self,
                    200,
                    {"jsonrpc": "2.0", "id": None, "error": {"code": -32602, "message": "Invalid params"}},
                )
                return

            bearer = _get_bearer(self.headers)
            start = time.monotonic()
            resp, status = handler.handle(payload=payload, bearer_token=bearer, raw_bytes=raw)
            duration_ms = int((time.monotonic() - start) * 1000)

            _send_json(self, status, resp)

            # Best-effort audit
            if getattr(handler.settings.audit, "enabled", False):
                _audit_line = {
                    "ts": time.time(),
                    "status": status,
                    "duration_ms": duration_ms,
                    "method": payload.get("method") if isinstance(payload, dict) else None,
                    "tool": (payload.get("params") or {}).get("name") if isinstance(payload, dict) else None,
                }
                if handler.settings.audit.log_payloads:
                    _audit_line["request"] = payload
                    _audit_line["response"] = resp
                _write_audit(handler.settings.audit.log_path, _audit_line)

        def log_message(self, fmt, *args):  # noqa: A003
            # Avoid noisy default HTTP logs; audit is handled separately.
            return

    class _Server(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = _Server((host, port), MCPHTTPHandler)
    logger.info("HTTP MCP gateway listening on http://%s:%d/mcp", host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down HTTP server")
        httpd.shutdown()


def _write_audit(path: Optional[str], line):
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        return
