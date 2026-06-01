# Cursor Guide (Odoo Online MCP Gateway)

Use this guide if you want Cursor to talk to **Odoo Online (SaaS)** without hosting anything. Cursor runs the gateway locally over **stdio**, and the gateway connects outbound to Odoo Online over **XML-RPC**.

## What you get

- Query live Odoo Online data from Cursor via MCP.
- The vendor-provided Docker image is **read-only** (no create/update/delete) and supports safe **aggregations** for dashboards.

## Docker Desktop setup (shipping method)

### Prerequisites

1) Docker Desktop installed and running
2) Your Odoo Online connection info:
   - `ODOO_BASE_URL` (example: `https://yourcompany.odoo.com`)
   - `ODOO_DB` (database name from Odoo Settings → About)
   - `ODOO_LOGIN` + `ODOO_PASSWORD` (password or API key)
3) A dedicated Odoo “integration user” (recommended)

### Files you should have from the vendor

You should receive:
- `odoo-online-mcp-gateway-readonly_0.1.1.tar.gz` (the Docker image bundle)
- `odoo-online-mcp-gateway-readonly_0.1.1.tar.gz.sha256` (optional integrity checksum)
- `env.example` (template for your `.env`)



### Step 1 — Load the Docker image

```bash
docker load -i odoo-online-mcp-gateway-readonly_0.1.1.tar.gz
```

Optional: verify checksum (recommended if the file was downloaded over email/drive):

```bash
shasum -a 256 odoo-online-mcp-gateway-readonly_0.1.1.tar.gz
# compare with the contents of odoo-online-mcp-gateway-readonly_0.1.1.tar.gz.sha256
```

### Step 2 — Create your `.env` (credentials live here)

Copy the template and fill values:

```bash
cp env.example .env
```

The `.env` file must include:
- `ODOO_BASE_URL`, `ODOO_DB`, `ODOO_LOGIN`, `ODOO_PASSWORD`
- `GATEWAY_TOKEN_1` and `GATEWAY_TOKEN` (set both to the same long random value)

Important: Docker env files must be `KEY=value` without quotes.

### Step 3 — Quick validation (recommended)

```bash
docker run --rm --env-file /ABS/PATH/.env odoo-online-mcp-gateway-readonly:0.1.1 \
  python -m odoo_online_mcp_gateway check
```

### Step 4 — Configure Cursor MCP (stdio via Docker)

Cursor needs to run a local command as an MCP server.

Use:
- **Command**: `docker`
- **Args**:
  1) `run`
  2) `--rm`
  3) `-i`
  4) `--env-file`
  5) `/ABS/PATH/.env`
  6) `odoo-online-mcp-gateway-readonly:0.1.1`

If your Cursor version supports editing an MCP JSON config directly, the equivalent looks like:

```json
{
  "mcpServers": {
    "odoo_online": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--env-file",
        "/ABS/PATH/.env",
        "odoo-online-mcp-gateway-readonly:0.1.1"
      ]
    }
  }
}
```

Restart Cursor (or reload MCP servers) so it starts the MCP server process.

### What models/tables can Cursor access in Docker mode?

In Docker mode, the policy (models/ops) is **baked into the image** you were provided.

Default Phase‑1 allowlist:
- `stock.picking`
- `sale.order`
- `res.partner`
- `account.move`
- `crm.lead`

If you need more models/fields/domains, you request an updated image/tag from the vendor.

## What can Cursor do (tools)?

Supported MCP tools:
- `list_models`
- `describe_model`
- `search_records`
- `get_record`
- `aggregate_records`

Optional write tools (off by default; require policy + `confirm=true`):
- `create_record`, `update_record`, `delete_record`

## Recommended first queries in Cursor

- “List the Odoo models I can access.”
- “Describe `res.partner` fields and what they mean.”
- “Search the last 20 `sale.order` records; return id, name, state, amount_total.”
- “Group `sale.order` by `state` and sum `amount_total`.”

## Tightening access (recommended)

Ask the vendor to provide an updated policy (new image/tag) if you need different models/ops/domains/fields.

## Troubleshooting

- “Unauthorized”: token mismatch (don’t change token values unless you also update `config.json`/`.env` consistently).
- “Odoo authentication failed”: base URL / DB / login / password/API key is wrong, or the user lacks app permissions.
- Enable debug logs by setting `GATEWAY_DEBUG="1"` in `.env` and restarting Cursor.
