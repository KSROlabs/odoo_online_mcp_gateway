# Odoo Online (SaaS) MCP Gateway — User Guide

This guide is for customers who use **Odoo Online / Odoo Cloud (odoo.com hosted SaaS)** and want to connect AI tools (Cursor / Claude Code / Claude Desktop) to live Odoo data via MCP.

For app-specific setup:
- Claude Desktop: `docs/CLAUDE_DESKTOP_GUIDE.md`
- Cursor: `docs/CURSOR_GUIDE.md`

## What this is
Odoo Online does **not** allow installing custom server modules.

So instead of running MCP *inside* Odoo, you run a small gateway **outside** Odoo (on your laptop, a VPS, or Docker). The gateway connects to Odoo Online using Odoo’s official APIs and exposes an MCP endpoint for your AI tools.

## What you can do
With the gateway you can:
- Search and read records (customers, orders, invoices, shipments)
- Describe models and fields (helps developers in Cursor/Claude Code)
- Aggregate data with `read_group` (dashboards)
- Optionally enable selective writes (with confirmation)

## Before you start (requirements)
You need:
- Your Odoo Online URL, for example: `https://yourcompany.odoo.com`
- Your database name (often similar to your subdomain)
- A dedicated Odoo “integration user” (recommended)
- Python 3.10+ or Docker

## Fastest production setup (recommended)
From the project folder, generate a ready-to-edit `.env` + `config.json`:

```bash
python3 -m odoo_online_mcp_gateway init
```

Then:
1) Edit `.env` and fill in your `ODOO_*` credentials
2) Start the gateway:

```bash
python3 -m odoo_online_mcp_gateway --env-file .env http --host 127.0.0.1 --port 8787
```

For Claude Desktop / Cursor (stdio mode):

```bash
python3 -m odoo_online_mcp_gateway --env-file .env stdio
```

If you are using a vendor-provided Docker image, you typically only need a local `.env` file with `ODOO_*` credentials and a `GATEWAY_TOKEN`, then Cursor runs the image via `docker run -i --env-file ...`.

### How to find your database name
Odoo Online still uses a database name for remote APIs.

Common ways to find it:
- In Odoo: enable Developer Mode, then open **Settings → About** (or the user menu → About) and look for **Database**.
- Ask your Odoo admin / Odoo support for the exact database name.

## Step 1 — Create an integration user (recommended)
In Odoo Online:
1. Create a user named something like **MCP Integration**
2. Give it access to only the apps you need (Sales, Inventory, CRM, Invoicing)
3. Keep it as “User”, not “Manager/Admin”

## Step 2 — Configure gateway credentials
Set these environment variables (example):

```bash
export ODOO_BASE_URL="https://yourcompany.odoo.com"
export ODOO_DB="yourcompany"
export ODOO_LOGIN="integration@yourcompany.com"
export ODOO_PASSWORD="YOUR_PASSWORD_OR_API_KEY"
```

Tip: you can put these in a local `.env` file and run the gateway with `--env-file .env` (see “Fastest production setup” above).
This is the recommended approach for Cursor/Claude so credentials don’t have to be pasted into the client app config.

## Step 3 — Configure gateway access tokens
You have two options:

### Option 1: Simple mode (`GATEWAY_TOKENS`)
Create a long random token and set:

```bash
export GATEWAY_TOKENS="PASTE_A_LONG_RANDOM_TOKEN_HERE"
```

This token is what your AI tools will use:
- `Authorization: Bearer <token>`

### Option 2: Production mode (`GATEWAY_CONFIG`)
Use a JSON config file with per-token policies (recommended for production). The `init` command generates a ready-to-edit `config.json`.

## Step 4 — Start the gateway (choose one)

### Option A (recommended for Cursor/Claude Desktop): Local stdio mode
This is the easiest and safest option for developers:
- No inbound port needed
- Runs locally and talks to Odoo Online directly

```bash
cd odoo_online_mcp_gateway
export GATEWAY_TOKEN="PASTE_A_LONG_RANDOM_TOKEN_HERE"
python3 -m odoo_online_mcp_gateway stdio
```

### Option B: Run with Python (HTTP mode)
```bash
cd odoo_online_mcp_gateway
python3 -m odoo_online_mcp_gateway http --host 127.0.0.1 --port 8787
```

### Option C: Run with Docker (HTTP mode)
```bash
cd odoo_online_mcp_gateway/docker
export GATEWAY_TOKEN_1="PASTE_A_LONG_RANDOM_TOKEN_HERE"
docker compose up --build
```

## Step 5 — Test it works
```bash
curl -X POST "http://localhost:8787/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer PASTE_A_LONG_RANDOM_TOKEN_HERE" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

If you get a tool list back, you are ready.

## Step 6 — Connect Cursor / Claude Code / Claude Desktop
Most MCP clients support either:
- HTTP MCP server, or
- stdio MCP server (a local command)

This gateway supports both:
- HTTP: use `http://localhost:8787/mcp` (or your hosted URL)
- stdio: run a local command and configure the client to execute it (recommended for Claude Desktop / Cursor)

### Claude Desktop configuration (stdio)
Claude Desktop expects a local command (it does not reliably load HTTP MCP servers directly).

Create/edit your `claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "odoo_saas": {
      "command": "python3",
      "args": ["/ABS/PATH/odoo_online_mcp_gateway/run_gateway.py", "--env-file", "/ABS/PATH/odoo_online_mcp_gateway/.env", "stdio"]
    }
  }
}
```

### Cursor / Claude Code configuration (stdio)
Cursor uses an MCP config with the same idea: run a local command and pass `env`.
Use the exact same `command` and `args` values shown above. If you use `--env-file`, you typically don’t need to pass secrets in the MCP client config.

## Step 7 — Validate connectivity (smoke test)
Before trying dashboards/analytics prompts, run:

```bash
python3 -m odoo_online_mcp_gateway --env-file .env check
```

This checks:
- Odoo authentication works
- Phase 1 models can be read/aggregated

## Default data scope (Phase 1)
The default allowlist is:
- `stock.picking`
- `sale.order`
- `res.partner`
- `account.move`
- `crm.lead`

To add more models, use `docker/config.example.json` and expand `allow_models`.

## Writes (create/update/delete)
Writes are disabled by default.
If you enable writes later, the gateway requires `confirm=true` in the request to prevent accidental changes.

## Troubleshooting

### “Odoo authentication failed”
Most common causes:
- Wrong `ODOO_DB` (database name)
- Wrong login/password
- The user is not active / has no access

Fix:
- Re-check your DB name and credentials.
- Run `python3 -m odoo_online_mcp_gateway check` again.

### “Unauthorized”
This means the gateway did not accept your token.

Fix:
- In HTTP mode, verify you send: `Authorization: Bearer <token>`
- In stdio mode (Claude Desktop), verify `GATEWAY_TOKEN` matches one of the tokens in `GATEWAY_TOKENS` (or config file token).

### “Forbidden: scope”
This means the gateway policy blocked the request:
- Model not allowlisted, or
- Operation not allowed, or
- Field restrictions are enabled and you requested a field not in the allowlist.

Fix:
- Add the model to `allow_models` and restart the gateway.
- Keep reads enabled (`allow_ops` includes `read` and `aggregate`).

### “Fault / AccessError”
This is returned by Odoo when the integration user lacks rights.

Fix:
- Give the integration user access to the relevant app (Sales/Inventory/CRM/Invoicing).
- Confirm access by running the `check` command.
