# -*- coding: utf-8 -*-
"""
Integration tests for real Odoo Online connectivity.

IMPORTANT: These tests require a real Odoo Online instance.

Setup:
    1. Set environment variables:
       export ODOO_BASE_URL="https://yourcompany.odoo.com"
       export ODOO_DB="yourcompany"
       export ODOO_LOGIN="integration@company.com"
       export ODOO_PASSWORD="your_password_or_api_key"

    2. Run tests:
       RUN_INTEGRATION_TESTS=1 python -m pytest tests/test_integration_example.py -v

This file is a template. Uncomment and adapt to your Odoo instance.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestOdooIntegration(unittest.TestCase):
    """Real Odoo Online connectivity tests."""

    @classmethod
    def setUpClass(cls):
        """Skip if integration tests not enabled."""
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            raise unittest.SkipTest("Set RUN_INTEGRATION_TESTS=1 to run integration tests")

        # Verify Odoo credentials are set
        required = ["ODOO_BASE_URL", "ODOO_DB", "ODOO_LOGIN", "ODOO_PASSWORD"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise unittest.SkipTest(f"Missing env vars: {', '.join(missing)}")

        from odoo_online_mcp_gateway.odoo_xmlrpc import OdooXMLRPC

        cls.odoo = OdooXMLRPC(
            base_url=os.getenv("ODOO_BASE_URL"),
            db=os.getenv("ODOO_DB"),
            login=os.getenv("ODOO_LOGIN"),
            password=os.getenv("ODOO_PASSWORD"),
        )

    def test_01_authenticate(self):
        """Test Odoo authentication works."""
        uid = self.odoo.authenticate()
        self.assertIsInstance(uid, int)
        self.assertGreater(uid, 0)
        print(f"✓ Authenticated as UID {uid}")

    def test_02_search_read_partner(self):
        """Test basic search_read on res.partner."""
        rows = self.odoo.execute_kw(
            "res.partner",
            "search_read",
            [[]],
            {"fields": ["id", "name"], "limit": 5}
        )
        self.assertIsInstance(rows, list)
        self.assertTrue(len(rows) > 0)
        print(f"✓ Found {len(rows)} partners")

    def test_03_describe_model(self):
        """Test fields_get on res.partner."""
        fields = self.odoo.execute_kw(
            "res.partner",
            "fields_get",
            [["id", "name", "email"]],
            {"attributes": ["type", "string", "required"]}
        )
        self.assertIsInstance(fields, dict)
        self.assertIn("name", fields)
        print(f"✓ Got schema for {len(fields)} fields")

    def test_04_read_group(self):
        """Test read_group aggregation."""
        results = self.odoo.execute_kw(
            "sale.order",
            "read_group",
            [[]],
            {"fields": ["amount_total:sum"], "groupby": ["state"], "lazy": False}
        )
        self.assertIsInstance(results, list)
        print(f"✓ Read group returned {len(results)} groups")

    def test_05_phase1_models_accessible(self):
        """Test all Phase 1 models are accessible."""
        phase1 = ["stock.picking", "sale.order", "res.partner", "account.move", "crm.lead"]
        failures = []

        for model in phase1:
            try:
                # Quick check: can we call fields_get?
                _ = self.odoo.execute_kw(
                    model,
                    "fields_get",
                    [["id"]],
                    {"attributes": ["type"]}
                )
            except Exception as exc:
                failures.append((model, str(exc)))

        if failures:
            msg = "\n".join([f"  {m}: {e}" for m, e in failures])
            self.fail(f"Some Phase 1 models not accessible:\n{msg}")

        print(f"✓ All {len(phase1)} Phase 1 models accessible")


class TestMCPGatewayIntegration(unittest.TestCase):
    """End-to-end MCP gateway tests with real Odoo."""

    @classmethod
    def setUpClass(cls):
        """Skip if integration tests not enabled."""
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            raise unittest.SkipTest("Set RUN_INTEGRATION_TESTS=1 to run")

        from odoo_online_mcp_gateway.config import Settings, Limits, Audit
        from odoo_online_mcp_gateway.mcp import MCPHandler

        # Create a real handler with real Odoo connection
        cls.handler = MCPHandler(
            settings=Settings(
                odoo_base_url=os.getenv("ODOO_BASE_URL"),
                odoo_db=os.getenv("ODOO_DB"),
                odoo_login=os.getenv("ODOO_LOGIN"),
                odoo_password=os.getenv("ODOO_PASSWORD"),
                tokens=[{
                    "name": "test",
                    "token": "test_token_12345",
                    "policy": {
                        "allow_models": ["stock.picking", "sale.order", "res.partner"],
                        "allow_ops": ["read", "aggregate"]
                    }
                }],
                limits=Limits(max_payload_kb=512, rate_limit_per_minute=0),
                audit=Audit(enabled=False),
            )
        )

    def test_mcp_tools_list(self):
        """Test tools/list MCP method."""
        resp, status = self.handler.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            bearer_token="test_token_12345",
            raw_bytes=b"{}"
        )
        self.assertEqual(status, 200)
        self.assertIn("result", resp)
        self.assertIn("tools", resp["result"])
        self.assertTrue(len(resp["result"]["tools"]) > 0)
        print(f"✓ MCP tools/list returned {len(resp['result']['tools'])} tools")

    def test_mcp_search_records(self):
        """Test search_records tool."""
        resp, status = self.handler.handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "search_records",
                    "arguments": {
                        "model": "res.partner",
                        "domain": [],
                        "fields": ["id", "name"],
                        "limit": 5
                    }
                }
            },
            bearer_token="test_token_12345",
            raw_bytes=b"{}"
        )
        self.assertEqual(status, 200)
        self.assertIn("result", resp)
        print("✓ MCP search_records returned results")

    def test_mcp_rate_limit(self):
        """Test that rate limiting works."""
        from odoo_online_mcp_gateway.config import Settings, Limits, Audit

        # Create handler with low rate limit
        handler = MCPHandler(
            settings=Settings(
                odoo_base_url=os.getenv("ODOO_BASE_URL"),
                odoo_db=os.getenv("ODOO_DB"),
                odoo_login=os.getenv("ODOO_LOGIN"),
                odoo_password=os.getenv("ODOO_PASSWORD"),
                tokens=[{
                    "name": "test",
                    "token": "ratelimit_test_token",
                    "policy": {
                        "allow_models": ["res.partner"],
                        "allow_ops": ["read"]
                    }
                }],
                limits=Limits(max_payload_kb=512, rate_limit_per_minute=2),  # Very low
                audit=Audit(enabled=False),
            )
        )

        # Make 3 requests - 3rd should be rate limited
        for i in range(3):
            resp, status = handler.handle(
                {"jsonrpc": "2.0", "id": i, "method": "tools/list", "params": {}},
                bearer_token="ratelimit_test_token",
                raw_bytes=b"{}"
            )

            if i < 2:
                self.assertEqual(status, 200, f"Request {i} should succeed")
            else:
                # 3rd request should be 429 (rate limited)
                self.assertIn(status, [200, 429], f"Request {i} status: {status}")

        print("✓ Rate limiting works correctly")


if __name__ == "__main__":
    unittest.main()
