# Claude Desktop Guide (Odoo Online MCP Gateway)

Use this guide if you want Claude Desktop to talk to **Odoo Online (SaaS)** without hosting anything. Claude will run the gateway locally over **stdio**, and the gateway will connect outbound to Odoo Online over **XML-RPC**.

## What you get

- Claude can **search/read** Odoo records, **describe** models/fields, and run **aggregations** (`read_group`) via MCP.
- By default, the gateway is **read-only** (writes can be enabled later, but are gated).

## Prerequisites

1) **Python 3.10+** installed on your computer
2) Your Odoo Online info:
   - `ODOO_BASE_URL` (example: `https://yourcompany.odoo.com`)
   - `ODOO_DB` (database name shown in Odoo Settings → About)
   - `ODOO_LOGIN` + `ODOO_PASSWORD` (password or API key)
3) A dedicated Odoo “integration user” (recommended, least privilege)

## Step 1 — Get the gateway code

Place the gateway folder somewhere stable, for example:
- macOS/Linux: `~/tools/odoo_online_mcp_gateway/`
- Windows: `C:\tools\odoo_online_mcp_gateway\`

This folder must contain:
- `run_gateway.py`
- `odoo_online_mcp_gateway/` (package directory)

## Step 2 — Generate a ready-to-edit config

From inside the gateway folder:

```bash
python3 -m odoo_online_mcp_gateway init
```

This creates:
- `.env` (your credentials + local token)
- `config.json` (what models/operations are allowed)

## Step 3 — Fill in your Odoo credentials

Edit `.env` and set:
- `ODOO_BASE_URL` (your Odoo Online URL)
- `ODOO_DB` (database name)
- `ODOO_LOGIN` (integration user email)
- `ODOO_PASSWORD` (password or API key)

You can also set these as environment variables directly, but using `.env` + `--env-file` is recommended so you don’t paste secrets into app configuration.

Security note: keep `.env` private. Don’t paste it into chat or commit it to git.

## Step 4 — Quick validation (recommended)

```bash
python3 -m odoo_online_mcp_gateway --env-file .env check
```

If this fails, fix credentials and re-run until it says `Result: OK`.

## Step 5 — Configure Claude Desktop (stdio MCP server)

You’ll add an MCP server entry that runs the gateway as a local command.

### Configuration snippet

Use absolute paths:

```json
{
  "mcpServers": {
    "odoo_online": {
      "command": "python3",
      "args": [
        "/ABS/PATH/odoo_online_mcp_gateway/run_gateway.py",
        "--env-file",
        "/ABS/PATH/odoo_online_mcp_gateway/.env",
        "stdio"
      ]
    }
  }
}
```

### Where is `claude_desktop_config.json`?

Common locations (may vary by OS/version):
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\\Claude\\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

If you already have a config file, merge the `mcpServers.odoo_online` block into it.

### Restart Claude Desktop

Fully quit and re-open Claude Desktop so it reloads the MCP configuration.

## Step 6 — What Claude can access (models/tables)

The gateway enforces an allowlist in `config.json`. By default the generated config allows:
- `stock.picking`
- `sale.order`
- `res.partner`
- `account.move`
- `crm.lead`

You can change this list in `config.json` under:
- `tokens[0].policy.allow_models`

Important: Odoo’s own permissions still apply. The integration user must have access to the apps/records.

## Step 7 — What Claude can do (tools)

Claude will use MCP tools. The gateway supports:

- `list_models` (shows allowlisted models for the token)
- `describe_model` (field metadata via `fields_get`)
- `search_records` (reads records via `search_read`)
- `get_record` (reads a specific id; also respects configured domain rules)
- `aggregate_records` (aggregates via `read_group`)

Optional (disabled unless enabled in policy + requires confirmation):
- `create_record`, `update_record`, `delete_record` (requires `confirm=true`)

## Step 8 — Recommended “first prompts” to try in Claude

- “List the Odoo models I’m allowed to access.”
- “Describe the `sale.order` model and its key fields.”
- “Find the last 20 sales orders and show id, name, state, amount_total.”
- “Aggregate sales orders by state and sum amount_total.”

## Tightening scope (recommended for customers)

In `config.json`, you can:
- Restrict operations: `allow_ops` (default is `["read","aggregate"]`)
- Restrict fields per model: `restrict_fields: true` + `allowed_fields`
- Restrict records per model: `domain` (for example, only customer invoices on `account.move`)

## Troubleshooting

- “Odoo authentication failed”: DB name, URL, login/password/API key, or user permissions are wrong.
- “Unauthorized”: token mismatch (the token in `.env` must match the policy token).
- Enable debug logs:
  - set `GATEWAY_DEBUG="1"` in `.env` and restart Claude Desktop.
