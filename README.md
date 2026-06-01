# Odoo Online (SaaS) MCP Gateway

This is a standalone MCP gateway that works with **Odoo Online / Odoo Cloud (odoo.com hosted SaaS)**.

Why it exists:
- Odoo Online does **not** allow installing custom server modules.
- But Odoo Online **does** support official remote APIs (XML-RPC / JSON-RPC).
- This gateway exposes an MCP endpoint and translates tool calls into Odoo API calls.

## What you can do
- Connect Cursor / Claude Code / Claude Desktop (via MCP) to Odoo Online
- Query live Odoo data (read-only by default)
- Run safe aggregates for dashboards (`read_group`)
- Optionally enable selective writes (with confirmation)

## Quick start (HTTP mode)
1) Create a dedicated Odoo integration user (recommended).
2) Export these environment variables:

```bash
export ODOO_BASE_URL="https://YOURTENANT.odoo.com"
export ODOO_DB="YOUR_DB"
export ODOO_LOGIN="integration@example.com"
export ODOO_PASSWORD="YOUR_PASSWORD_OR_API_KEY"

export GATEWAY_TOKENS="CHANGE_ME_TO_A_LONG_RANDOM_TOKEN"
```

### Even faster (recommended)
Generate a starter `.env` and `config.json`, then edit `.env` with your Odoo credentials:

```bash
python3 -m odoo_online_mcp_gateway init
python3 -m odoo_online_mcp_gateway --env-file .env http --host 0.0.0.0 --port 8787
```

3) Run the gateway:

```bash
python3 -m odoo_online_mcp_gateway http --host 0.0.0.0 --port 8787
```

4) Test:

```bash
curl -X POST "http://localhost:8787/mcp" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer CHANGE_ME_TO_A_LONG_RANDOM_TOKEN" \\
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Quick start (stdio mode for Cursor/Claude Code)
Some clients prefer MCP over stdio. Run:

```bash
python3 -m odoo_online_mcp_gateway stdio
```

Then configure your client to run the command with the same environment variables.

### Claude Desktop / Cursor config (stdio)
Most desktop MCP clients expect a local command (stdio). Use the included helper script:

```json
{
  "mcpServers": {
    "odoo_saas": {
      "command": "python3",
      "args": ["/ABS/PATH/odoo_online_mcp_gateway/run_gateway.py", "stdio"],
      "env": {
        "ODOO_BASE_URL": "https://YOURTENANT.odoo.com",
        "ODOO_DB": "YOUR_DB",
        "ODOO_LOGIN": "integration@example.com",
        "ODOO_PASSWORD": "YOUR_PASSWORD_OR_API_KEY",
        "GATEWAY_TOKENS": "CHANGE_ME_TO_A_LONG_RANDOM_TOKEN",
        "GATEWAY_TOKEN": "CHANGE_ME_TO_A_LONG_RANDOM_TOKEN"
      }
    }
  }
}
```

Notes:
- `GATEWAY_TOKENS` defines which tokens are valid on the gateway.
- `GATEWAY_TOKEN` is the token used by the local stdio client (Claude/Cursor) to authenticate to the gateway logic.

## Configuration
You can configure policy in two ways:
- Environment variables (simple)
- A JSON config file (recommended for production)

See `docker/config.example.json`.

## Smoke test (recommended)
Before connecting an AI tool, verify your Odoo Online credentials work:

```bash
python3 -m odoo_online_mcp_gateway check
```

## Notes on writes
Writes are **disabled by default**.
If you enable write tools, the gateway requires `confirm=true` for create/update/delete calls.

## License / Distribution
This gateway is designed to be distributed alongside your Odoo App Store module as the “Odoo Online edition”.
# odoo_online_mcp_gateway
