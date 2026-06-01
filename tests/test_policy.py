# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from odoo_online_mcp_gateway.policy import PolicyEngine, PolicyError  # noqa: E402


class TestPolicyEngine(unittest.TestCase):
    def test_auth_success(self):
        engine = PolicyEngine(
            tokens_cfg=[{"name": "t1", "token": "abc", "policy": {"allow_models": ["res.partner"], "allow_ops": ["read"]}}],
            rate_limit_per_minute=0,
        )
        pol = engine.authenticate("abc")
        self.assertIn("res.partner", pol.allow_models)

    def test_auth_fail(self):
        engine = PolicyEngine(tokens_cfg=[{"name": "t1", "token": "abc", "policy": {"allow_models": [], "allow_ops": ["read"]}}], rate_limit_per_minute=0)
        with self.assertRaises(PolicyError):
            engine.authenticate("wrong")

    def test_scope_model(self):
        engine = PolicyEngine(tokens_cfg=[{"name": "t1", "token": "abc", "policy": {"allow_models": ["sale.order"], "allow_ops": ["read"]}}], rate_limit_per_minute=0)
        pol = engine.authenticate("abc")
        with self.assertRaises(PolicyError):
            engine.ensure_model_allowed(pol, "res.partner")

    def test_scope_op(self):
        engine = PolicyEngine(tokens_cfg=[{"name": "t1", "token": "abc", "policy": {"allow_models": ["res.partner"], "allow_ops": ["read"]}}], rate_limit_per_minute=0)
        pol = engine.authenticate("abc")
        with self.assertRaises(PolicyError):
            engine.ensure_op_allowed(pol, "aggregate")
