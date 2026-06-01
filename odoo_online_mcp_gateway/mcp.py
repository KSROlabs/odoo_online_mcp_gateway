# -*- coding: utf-8 -*-
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .config import Settings
from .odoo_xmlrpc import OdooXMLRPC
from .policy import PolicyEngine, PolicyError

logger = logging.getLogger(__name__)


class MCPHandler:
    """
    Implements JSON-RPC 2.0 methods used by MCP clients:
    - initialize
    - tools/list
    - tools/call
    - ping
    - resources/list (empty)
    - prompts/list (empty)
    """

    TOOL_SPECS: Dict[str, Dict[str, Any]] = {
        "list_models": {
            "description": "List models available to this gateway token.",
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        "describe_model": {
            "description": "Describe a model and its fields.",
            "input_schema": {
                "type": "object",
                "properties": {"model": {"type": "string"}},
                "required": ["model"],
                "additionalProperties": False,
            },
        },
        "search_records": {
            "description": "Search and read records from a model.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string"},
                    "domain": {"type": "array", "items": {}},
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                    "offset": {"type": "integer"},
                    "order": {"type": "string"},
                },
                "required": ["model"],
                "additionalProperties": False,
            },
        },
        "get_record": {
            "description": "Get a single record by id.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string"},
                    "id": {"type": "integer"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["model", "id"],
                "additionalProperties": False,
            },
        },
        "aggregate_records": {
            "description": "Aggregate records with group-by and metrics.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string"},
                    "domain": {"type": "array", "items": {}},
                    "metrics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "agg": {"type": "string"},
                                "label": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                    },
                    "groupby": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
                "required": ["model"],
                "additionalProperties": False,
            },
        },
        "create_record": {
            "description": "Create a record (disabled by default; requires confirm=true).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "confirm": {"type": "boolean"},
                    "model": {"type": "string"},
                    "values": {"type": "object"},
                },
                "required": ["model", "values"],
                "additionalProperties": False,
            },
        },
        "update_record": {
            "description": "Update a record (disabled by default; requires confirm=true).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "confirm": {"type": "boolean"},
                    "model": {"type": "string"},
                    "id": {"type": "integer"},
                    "values": {"type": "object"},
                },
                "required": ["model", "id", "values"],
                "additionalProperties": False,
            },
        },
        "delete_record": {
            "description": "Delete a record (disabled by default; requires confirm=true).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "confirm": {"type": "boolean"},
                    "model": {"type": "string"},
                    "id": {"type": "integer"},
                },
                "required": ["model", "id"],
                "additionalProperties": False,
            },
        },
    }

    def __init__(self, settings: Settings):
        self.settings = settings
        self.policy = PolicyEngine(settings.tokens, settings.limits.rate_limit_per_minute)
        self.odoo = OdooXMLRPC(
            base_url=settings.odoo_base_url,
            db=settings.odoo_db,
            login=settings.odoo_login,
            password=settings.odoo_password,
        )

    def handle(self, payload: Any, bearer_token: Optional[str], raw_bytes: Optional[bytes] = None) -> Tuple[Dict[str, Any], int]:
        """
        Handle a single MCP JSON-RPC 2.0 request.

        Args:
            payload: Decoded JSON request object
            bearer_token: Bearer token from Authorization header (may be empty)
            raw_bytes: Original request bytes for size validation

        Returns:
            Tuple of (response_dict, http_status_code)

        Raises:
            PolicyError: If auth, rate limit, or scope check fails
        """
        start = time.monotonic()
        http_status = 200

        try:
            if raw_bytes is not None:
                self._check_payload_size(raw_bytes)
            request_obj = payload
            if not isinstance(request_obj, dict):
                return self._error(None, -32602, "Invalid params"), 200

            if request_obj.get("jsonrpc") != "2.0":
                return self._error(request_obj.get("id"), -32602, "Invalid params"), 200

            rpc_id = request_obj.get("id")
            method = request_obj.get("method")
            params = request_obj.get("params") or {}

            if method in ("resources/list", "prompts/list"):
                return self._result(rpc_id, {"resources": []} if method == "resources/list" else {"prompts": []}), 200
            if method == "ping":
                return self._result(rpc_id, {}), 200
            if method == "initialize":
                return self._result(rpc_id, self._initialize()), 200
            if method == "tools/list":
                pol = self.policy.authenticate(bearer_token or "")
                return self._result(rpc_id, self._tools_list(pol)), 200
            if method == "tools/call":
                pol = self.policy.authenticate(bearer_token or "")
                if not isinstance(params, dict):
                    return self._error(rpc_id, -32602, "Invalid params"), 200
                tool_name = params.get("name")
                arguments = params.get("arguments") or {}
                if not isinstance(tool_name, str) or not isinstance(arguments, dict):
                    return self._error(rpc_id, -32602, "Invalid params"), 200
                self._validate_tool_arguments(tool_name, arguments)
                result = self._tools_call(pol, tool_name, arguments)
                return self._result(rpc_id, result), 200

            return self._error(rpc_id, -32601, "Method not found"), 200
        except PolicyError as exc:
            msg = str(exc)
            if msg == "Unauthorized":
                return self._error(payload.get("id") if isinstance(payload, dict) else None, -32001, msg), 401
            if msg == "Payload too large":
                return self._error(payload.get("id") if isinstance(payload, dict) else None, -32602, "Invalid params", data=msg), 413
            if msg.startswith("Rate limit exceeded"):
                return self._error(payload.get("id") if isinstance(payload, dict) else None, -32002, "Forbidden", data=msg), 429
            # Scope violations (model/op/field restrictions)
            if msg.startswith("Model '") or msg.startswith("Operation '") or msg.startswith("Fields not allowed"):
                return self._error(payload.get("id") if isinstance(payload, dict) else None, -32003, msg), 403
            if "Invalid params" in msg or "Method not found" in msg:
                return self._error(payload.get("id") if isinstance(payload, dict) else None, -32602, "Invalid params", data=msg), 200
            return self._error(payload.get("id") if isinstance(payload, dict) else None, -32002, "Forbidden", data=msg), 403
        except Exception as exc:
            logger.exception("Unhandled error during MCP request")
            if self.settings.hide_internal_errors:
                return self._error(payload.get("id") if isinstance(payload, dict) else None, -32603, "Internal error"), 500
            return self._error(payload.get("id") if isinstance(payload, dict) else None, -32603, "Internal error", data=str(exc)), 500
        finally:
            _ = start  # reserved for audit; handled by server wrapper

    def _initialize(self) -> Dict[str, Any]:
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "odoo_online_mcp_gateway", "version": "0.1.1"},
            "capabilities": {"tools": {"list": True, "call": True}, "resources": {"list": True}, "prompts": {"list": True}},
        }

    def _tools_list(self, pol) -> Dict[str, Any]:
        tools = []
        for name, spec in self.TOOL_SPECS.items():
            if name == "create_record" and "create" not in pol.allow_ops:
                continue
            if name == "update_record" and "write" not in pol.allow_ops:
                continue
            if name == "delete_record" and "unlink" not in pol.allow_ops:
                continue
            if name == "aggregate_records" and "aggregate" not in pol.allow_ops:
                continue
            if name in ("describe_model", "search_records", "get_record", "list_models") and "read" not in pol.allow_ops:
                continue
            # MCP clients vary: most accept `input_schema`; some accept camelCase.
            schema = spec.get("input_schema") or {}
            tools.append({"name": name, "description": spec["description"], "input_schema": schema, "inputSchema": schema})
        return {"tools": tools}

    def _tools_call(self, pol, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single MCP tool.

        Args:
            pol: TokenPolicy for the authenticated token
            tool_name: Name of the tool to execute
            args: Arguments passed to the tool

        Returns:
            MCP content response dict with type and text
        """
        if tool_name == "list_models":
            return {"content": [{"type": "text", "text": json.dumps({"models": sorted(list(pol.allow_models))})}]}
        if tool_name == "describe_model":
            model = args.get("model")
            self.policy.ensure_model_allowed(pol, model)
            self.policy.ensure_op_allowed(pol, "read")
            fields = self.odoo.execute_kw(model, "fields_get", [], {"attributes": ["type", "string", "required", "readonly", "relation"]})
            # Apply optional field allowlist (if configured for this model)
            rule = pol.model_rules.get(model)
            if rule and rule.restrict_fields and rule.allowed_fields is not None:
                fields = {k: v for k, v in fields.items() if k in rule.allowed_fields}
            return {"content": [{"type": "text", "text": json.dumps({"model": model, "fields": fields})}]}
        if tool_name == "search_records":
            model = args.get("model")
            domain = args.get("domain") or []
            fields_list = args.get("fields") or []
            limit = self._clamp_limit(args.get("limit"), default=20, max_limit=500)
            offset = self._clamp_offset(args.get("offset"))
            order = args.get("order")
            self.policy.ensure_model_allowed(pol, model)
            self.policy.ensure_op_allowed(pol, "read")
            if fields_list:
                self.policy.enforce_fields(pol, model, fields_list)
            domain = self.policy.apply_domain(pol, model, domain)
            kw = {"fields": fields_list, "limit": limit, "offset": offset}
            if order:
                kw["order"] = order
            rows = self.odoo.execute_kw(model, "search_read", [domain], kw)
            return {"content": [{"type": "text", "text": json.dumps({"records": rows})}]}
        if tool_name == "get_record":
            model = args.get("model")
            rid = args.get("id")
            fields_list = args.get("fields") or []
            self.policy.ensure_model_allowed(pol, model)
            self.policy.ensure_op_allowed(pol, "read")
            if fields_list:
                self.policy.enforce_fields(pol, model, fields_list)
            domain = self.policy.apply_domain(pol, model, [])
            # enforce domain by verifying record is in search
            ids = self.odoo.execute_kw(model, "search", [domain + [["id", "=", rid]]], {"limit": 1})
            if not ids:
                return {"content": [{"type": "text", "text": "Not found"}], "isError": True}
            recs = self.odoo.execute_kw(model, "read", [[rid]], {"fields": fields_list} if fields_list else {})
            rec = recs[0] if recs else None
            return {"content": [{"type": "text", "text": json.dumps({"record": rec})}]}
        if tool_name == "aggregate_records":
            model = args.get("model")
            domain = args.get("domain") or []
            metrics = args.get("metrics") or []
            groupby = args.get("groupby") or []
            limit = self._clamp_limit(args.get("limit"), default=None, max_limit=1000) if args.get("limit") else None
            self.policy.ensure_model_allowed(pol, model)
            self.policy.ensure_op_allowed(pol, "aggregate")
            # Enforce optional field allowlist for groupby + metric fields.
            fields_to_check: List[str] = []
            for gb in groupby:
                if isinstance(gb, str):
                    fields_to_check.append(gb.split(":")[0])
            for m in metrics:
                if isinstance(m, dict) and m.get("field"):
                    fields_to_check.append(str(m.get("field")))
            if fields_to_check:
                self.policy.enforce_fields(pol, model, list(set(fields_to_check)))
            domain = self.policy.apply_domain(pol, model, domain)
            fields = []
            for m in metrics:
                if not isinstance(m, dict):
                    continue
                agg = m.get("agg") or "count"
                field = m.get("field")
                if agg == "count":
                    continue
                if field:
                    fields.append("%s:%s" % (field, agg))
            kwargs = {"lazy": False}
            if limit is not None:
                kwargs["limit"] = limit
            rows = self.odoo.execute_kw(model, "read_group", [domain, fields, groupby], kwargs)
            return {"content": [{"type": "text", "text": json.dumps({"results": rows})}]}
        if tool_name in ("create_record", "update_record", "delete_record"):
            return self._write_tool(pol, tool_name, args)

        return {"content": [{"type": "text", "text": "Unknown tool"}], "isError": True}

    def _write_tool(self, pol, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        confirm = bool(args.get("confirm"))
        if not confirm:
            return {"content": [{"type": "text", "text": "Write requires confirmation (confirm=true)"}], "isError": True}

        model = args.get("model")
        self.policy.ensure_model_allowed(pol, model)

        if tool_name == "create_record":
            self.policy.ensure_op_allowed(pol, "create")
            values = args.get("values") or {}
            self.policy.enforce_fields(pol, model, list(values.keys()))
            rid = self.odoo.execute_kw(model, "create", [values], {})
            return {"content": [{"type": "text", "text": json.dumps({"id": rid})}]}
        if tool_name == "update_record":
            self.policy.ensure_op_allowed(pol, "write")
            rid = args.get("id")
            values = args.get("values") or {}
            self.policy.enforce_fields(pol, model, list(values.keys()))
            ok = self.odoo.execute_kw(model, "write", [[rid], values], {})
            return {"content": [{"type": "text", "text": json.dumps({"updated": bool(ok)})}]}
        if tool_name == "delete_record":
            self.policy.ensure_op_allowed(pol, "unlink")
            rid = args.get("id")
            ok = self.odoo.execute_kw(model, "unlink", [[rid]], {})
            return {"content": [{"type": "text", "text": json.dumps({"deleted": bool(ok)})}]}

        return {"content": [{"type": "text", "text": "Write tool not implemented"}], "isError": True}

    def _check_payload_size(self, raw_bytes: bytes):
        """Validate request payload size against configured limit."""
        max_kb = int(self.settings.limits.max_payload_kb or 0)
        if max_kb <= 0:
            return
        if len(raw_bytes) > max_kb * 1024:
            raise PolicyError("Payload too large")

    def _clamp_limit(self, limit: Optional[int], default: int = 20, max_limit: int = 500) -> int:
        """
        Clamp search limit to safe range.

        Args:
            limit: User-requested limit (may be None, negative, or extremely large)
            default: Default limit if not specified (default: 20)
            max_limit: Maximum allowed limit (default: 500)

        Returns:
            Clamped limit value
        """
        if limit is None or limit <= 0:
            return default
        return min(int(limit), max_limit)

    def _clamp_offset(self, offset: Optional[int]) -> int:
        """Clamp offset to non-negative integer."""
        return max(0, int(offset or 0))

    def _validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]):
        """
        Validate tool arguments against the schema.

        Args:
            tool_name: Name of the tool
            arguments: Arguments provided by caller

        Raises:
            PolicyError: If validation fails
        """
        if tool_name not in self.TOOL_SPECS:
            raise PolicyError("Method not found")
        schema = self.TOOL_SPECS[tool_name].get("input_schema") or {}
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        for r in required:
            if r not in arguments:
                raise PolicyError("Invalid params")
        if schema.get("additionalProperties") is False:
            for k in arguments.keys():
                if k not in props:
                    raise PolicyError("Invalid params")
        # Type validation (minimal JSON schema support)
        for k, v in arguments.items():
            expected = props.get(k) or {}
            if expected and not self._value_matches_schema(v, expected):
                raise PolicyError("Invalid params")

    def _value_matches_schema(self, value: Any, schema: Dict[str, Any]) -> bool:
        t = schema.get("type")
        if t == "string":
            return isinstance(value, str)
        if t == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if t == "boolean":
            return isinstance(value, bool)
        if t == "object":
            return isinstance(value, dict)
        if t == "array":
            if not isinstance(value, list):
                return False
            items = schema.get("items") or {}
            if not items:
                return True
            return all(self._value_matches_schema(item, items) for item in value)
        return True

    def _result(self, rpc_id, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}

    def _error(self, rpc_id, code: int, message: str, data: Optional[str] = None) -> Dict[str, Any]:
        err: Dict[str, Any] = {"code": code, "message": message}
        if data:
            err["data"] = data
        return {"jsonrpc": "2.0", "id": rpc_id, "error": err}
