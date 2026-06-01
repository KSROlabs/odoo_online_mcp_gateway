# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import time
import unittest


class TestStdioTransport(unittest.TestCase):
    def test_stdout_is_ndjson_by_default(self):
        env = os.environ.copy()
        # Force default behavior (no legacy framing env vars set)
        env.pop("MCP_STDIO_FRAMING", None)
        env.pop("GATEWAY_STDIO_FRAMING", None)
        # Minimal required settings so CLI can start (initialize does not contact Odoo).
        env["ODOO_BASE_URL"] = "https://example.odoo.com"
        env["ODOO_DB"] = "example"
        env["ODOO_LOGIN"] = "user@example.com"
        env["ODOO_PASSWORD"] = "x"
        env["GATEWAY_TOKENS"] = "testtoken"
        env["GATEWAY_TOKEN"] = "testtoken"
        env["GATEWAY_AUDIT_ENABLED"] = "0"

        proc = subprocess.Popen(
            [sys.executable, "-m", "odoo_online_mcp_gateway", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        try:
            req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
            }
            line = (json.dumps(req) + "\n").encode("utf-8")
            proc.stdin.write(line)
            proc.stdin.flush()

            out_line = proc.stdout.readline()
            self.assertTrue(out_line, msg="No response line from stdio server")
            self.assertFalse(out_line.startswith(b"Content-Length:"), msg=out_line[:50])
            obj = json.loads(out_line.decode("utf-8"))
            self.assertIn("result", obj)
        finally:
            if proc.stdin:
                proc.stdin.close()
            for _ in range(50):
                if proc.poll() is not None:
                    break
                time.sleep(0.02)
            if proc.poll() is None:
                proc.kill()
