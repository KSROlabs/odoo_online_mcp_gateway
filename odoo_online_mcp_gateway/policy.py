# -*- coding: utf-8 -*-
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


class PolicyError(Exception):
    pass


@dataclass
class ModelRule:
    domain: List[Any]
    restrict_fields: bool = False
    allowed_fields: Optional[Set[str]] = None


@dataclass
class TokenPolicy:
    name: str
    token_hash: str
    allow_models: Set[str]
    allow_ops: Set[str]
    model_rules: Dict[str, ModelRule]


@dataclass
class RateState:
    window_start: float
    count: int


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_allowed_fields(raw: Any) -> Optional[Set[str]]:
    if raw is None:
        return None
    if isinstance(raw, list):
        return {str(x) for x in raw if x}
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return set()
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return {str(x) for x in data if x}
        except Exception:
            pass
        return {p.strip() for p in s.split(",") if p.strip()}
    return None


def _ensure_domain(domain: Any) -> List[Any]:
    if domain is None:
        return []
    if not isinstance(domain, list):
        raise PolicyError("Domain must be a JSON array")
    return domain


class PolicyEngine:
    def __init__(self, tokens_cfg: List[Dict[str, Any]], rate_limit_per_minute: int):
        self._policies: Dict[str, TokenPolicy] = {}
        self._rate_limit = max(int(rate_limit_per_minute or 0), 0)
        self._rate_state: Dict[str, RateState] = {}
        self._load_tokens(tokens_cfg)

    def _load_tokens(self, tokens_cfg: List[Dict[str, Any]]):
        """Load and normalize token configurations."""
        for entry in tokens_cfg:
            token = entry.get("token")
            if not token:
                continue
            name = entry.get("name") or "token"
            policy = entry.get("policy") or {}
            allow_models = set(policy.get("allow_models") or [])
            allow_ops = set(policy.get("allow_ops") or ["read", "aggregate"])

            model_rules: Dict[str, ModelRule] = {}
            rules_cfg = policy.get("model_rules") or {}
            for model_name, rule_cfg in rules_cfg.items():
                domain = _ensure_domain(rule_cfg.get("domain"))
                restrict_fields = bool(rule_cfg.get("restrict_fields", False))
                allowed_fields = _parse_allowed_fields(rule_cfg.get("allowed_fields"))
                model_rules[model_name] = ModelRule(
                    domain=domain,
                    restrict_fields=restrict_fields,
                    allowed_fields=allowed_fields,
                )

            tp = TokenPolicy(
                name=name,
                token_hash=_sha256(token),
                allow_models=allow_models,
                allow_ops=allow_ops,
                model_rules=model_rules,
            )
            self._policies[tp.token_hash] = tp

    def authenticate(self, bearer_token: str) -> TokenPolicy:
        """
        Authenticate a bearer token and return its policy.

        Args:
            bearer_token: Bearer token to authenticate

        Returns:
            TokenPolicy for the authenticated token

        Raises:
            PolicyError: If token is invalid or rate limit exceeded
        """
        if not bearer_token:
            raise PolicyError("Unauthorized")
        token_hash = _sha256(bearer_token)
        policy = self._policies.get(token_hash)
        if not policy:
            raise PolicyError("Unauthorized")
        self._check_rate_limit(token_hash)
        return policy

    def _check_rate_limit(self, token_hash: str):
        """Check and enforce rate limit for a token."""
        if not self._rate_limit:
            return
        now = time.time()
        state = self._rate_state.get(token_hash)
        if not state or now - state.window_start >= 60:
            self._rate_state[token_hash] = RateState(window_start=now, count=1)
            return
        state.count += 1
        if state.count > self._rate_limit:
            raise PolicyError(
                f"Rate limit exceeded: {self._rate_limit} requests/minute. "
                f"Current count: {state.count}. Try again in ~60 seconds."
            )

    def ensure_model_allowed(self, policy: TokenPolicy, model: str):
        """Verify that a model is allowed for this token."""
        if model not in policy.allow_models:
            available = ", ".join(sorted(policy.allow_models)) if policy.allow_models else "(none)"
            raise PolicyError(
                f"Model '{model}' not allowed for this token. "
                f"Available models: {available}"
            )

    def ensure_op_allowed(self, policy: TokenPolicy, op: str):
        """Verify that an operation is allowed for this token."""
        if op not in policy.allow_ops:
            available = ", ".join(sorted(policy.allow_ops)) if policy.allow_ops else "(none)"
            raise PolicyError(
                f"Operation '{op}' not allowed for this token. "
                f"Allowed operations: {available}"
            )

    def apply_domain(self, policy: TokenPolicy, model: str, domain: List[Any]) -> List[Any]:
        """Apply token-level domain restrictions to a search domain."""
        rule = policy.model_rules.get(model)
        if not rule or not rule.domain:
            return domain
        return domain + rule.domain

    def enforce_fields(self, policy: TokenPolicy, model: str, fields: Optional[List[str]]):
        """Verify that requested fields are allowed for this token on this model."""
        rule = policy.model_rules.get(model)
        if not rule or not rule.restrict_fields:
            return
        allowed = rule.allowed_fields or set()
        req_fields = fields or []
        disallowed = [f for f in req_fields if f not in allowed]
        if disallowed:
            available = ", ".join(sorted(allowed)) if allowed else "(none)"
            raise PolicyError(
                f"Fields not allowed for this token on model '{model}': {', '.join(disallowed)}. "
                f"Allowed fields: {available}"
            )

