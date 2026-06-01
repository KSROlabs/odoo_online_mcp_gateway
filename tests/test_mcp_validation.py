# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from odoo_online_mcp_gateway.config import Settings, Limits, Audit  # noqa: E402
from odoo_online_mcp_gateway.mcp import MCPHandler  # noqa: E402


class _FakeOdoo:
    def __init__(self):
        self.calls = []

    def execute_kw(self, model, method, args, kwargs=None):
        self.calls.append((model, method, args, kwargs or {}))
        if method == "fields_get":
            return {"name": {"type": "char"}}
        if method == "search_read":
            return [{"id": 1, "name": "A"}]
        if method == "read_group":
            return [{"__count": 1}]
        if method == "search":
            return [1]
        if method == "read":
            return [{"id": 1, "name": "A"}]
        return True


class TestMCPValidation(unittest.TestCase):
    def _handler(self):
        s = Settings(
            odoo_base_url="https://x.odoo.com",
            odoo_db="x",
            odoo_login="x",
            odoo_password="x",
            tokens=[{"name": "t", "token": "abc", "policy": {"allow_models": ["res.partner"], "allow_ops": ["read", "aggregate"]}}],
            limits=Limits(max_payload_kb=1, rate_limit_per_minute=0),
            audit=Audit(enabled=False),
        )
        h = MCPHandler(settings=s)
        h.odoo = _FakeOdoo()
        return h

    def test_tools_list(self):
        h = self._handler()
        resp, status = h.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, bearer_token="abc", raw_bytes=b"{}")
        self.assertEqual(status, 200)
        self.assertIn("result", resp)
        self.assertIn("tools", resp["result"])
        self.assertTrue(resp["result"]["tools"])
        self.assertIn("input_schema", resp["result"]["tools"][0])

    def test_search_records(self):
        h = self._handler()
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "search_records", "arguments": {"model": "res.partner", "domain": [], "fields": ["name"], "limit": 1}},
        }
        resp, status = h.handle(payload, bearer_token="abc", raw_bytes=b"{}")
        self.assertEqual(status, 200)
        self.assertIn("result", resp)

    def test_invalid_args(self):
        h = self._handler()
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "search_records", "arguments": {"model": "res.partner", "domain": "bad"}},
        }
        resp, status = h.handle(payload, bearer_token="abc", raw_bytes=b"{}")
        self.assertEqual(status, 200)
        self.assertIn("error", resp)
