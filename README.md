# Odoo Online MCP Gateway

> **Connect AI tools (Claude, Cursor, any MCP client) to Odoo Online/SaaS — no server module required.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol](https://img.shields.io/badge/MCP-2024--11--05-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.1-orange.svg)](pyproject.toml)

---

## The Problem This Solves

Odoo Online (the cloud SaaS at `*.odoo.com`) **does not allow installing custom server modules**. This means every existing Odoo–AI integration that ships as an Odoo module simply doesn't work for the millions of companies on Odoo Online.

**This gateway bridges that gap.** It runs outside of Odoo, uses the official Odoo XML-RPC API (always available on all Odoo editions including SaaS), and speaks the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — the standard AI tool protocol supported by Claude Desktop, Cursor, Claude Code, and more.

```
 ┌──────────────────────────┐        ┌────────────────────────────┐        ┌─────────────────────┐
 │  AI Client               │  MCP   │  Odoo Online MCP Gateway   │ XML-RPC│  Odoo Online / SaaS │
 │  (Claude / Cursor / etc) │◄──────►│  (this project)            │◄──────►│  (*.odoo.com)       │
 └──────────────────────────┘        └────────────────────────────┘        └─────────────────────┘
     stdio or HTTP transport              token auth + policy engine             official API
```

**No Odoo module to install. No Odoo server access needed. Works with Odoo Online out of the box.**

---

## What You Can Do

Once connected, your AI can:

- **Browse Odoo data naturally** — "Show me the last 20 sales orders that are in progress"
- **Understand your data model** — "What fields does `res.partner` have?"
- **Run business analytics** — "Aggregate sales by salesperson for this month and sum the revenue"
- **Get records by ID** — "Get me the details of invoice INV/2024/0042"
- **Optionally write** — Create, update, or delete records (disabled by default, requires explicit confirmation)

All of this works on **Odoo 16, 17, 18** and any Odoo Online / Odoo Cloud instance.

---

## Supported AI Clients

| Client | Transport | Guide |
|--------|-----------|-------|
| **Claude Desktop** | stdio | [Claude Desktop Guide](docs/CLAUDE_DESKTOP_GUIDE.md) |
| **Cursor** | stdio (Docker) | [Cursor Guide](docs/CURSOR_GUIDE.md) |
| **Claude Code (CLI)** | stdio or HTTP | [Quick Start below](#quick-start) |
| **Any MCP-compatible client** | HTTP POST `/mcp` | [HTTP Mode](#http-mode-for-servers--remote-access) |

---

## Quick Start

### Prerequisites

- Python 3.10 or newer
- Your Odoo Online credentials:
  - `ODOO_BASE_URL` — e.g., `https://yourcompany.odoo.com`
  - `ODOO_DB` — database name (Settings → About → Database)
  - `ODOO_LOGIN` — user email
  - `ODOO_PASSWORD` — password or API key

**Security tip:** Create a dedicated **integration user** in Odoo with access only to the apps you need. Never use your admin account.

---

### Option A — Auto-generate config (recommended)

```bash
# Clone the repository
git clone https://github.com/KSROlabs/odoo_online_mcp_gateway.git
cd odoo_online_mcp_gateway

# Generate .env and config.json with a secure random token
python3 -m odoo_online_mcp_gateway init

# Edit .env and fill in your Odoo credentials
nano .env   # or: code .env / vim .env

# Verify the connection works
python3 -m odoo_online_mcp_gateway --env-file .env check

# Start the gateway
python3 -m odoo_online_mcp_gateway --env-file .env http
```

The gateway is now listening on `http://127.0.0.1:8787/mcp`. ✅

---

### Option B — Environment variables (quickest for testing)

```bash
export ODOO_BASE_URL="https://yourcompany.odoo.com"
export ODOO_DB="yourcompany"
export ODOO_LOGIN="integration@yourcompany.com"
export ODOO_PASSWORD="your_password_or_api_key"
export GATEWAY_TOKENS="replace_with_a_long_random_token"

python3 -m odoo_online_mcp_gateway http
```

---

### Option C — Docker

```bash
cd docker

# Copy env template and fill in credentials
cp env.example .env
nano .env

# Start with Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f
```

---

### Test It's Working

```bash
# Replace YOUR_TOKEN with the token you set in .env / GATEWAY_TOKENS
curl -s -X POST "http://localhost:8787/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 -m json.tool
```

You should see a list of available MCP tools. If you do, your gateway is fully operational.

---

## Connecting to Claude Desktop (stdio)

Claude Desktop runs the gateway as a local subprocess using stdio transport — **no server to host**.

**Step 1** — Run `init` and `check` to confirm credentials work (see above).

**Step 2** — Add this to your `claude_desktop_config.json` (use absolute paths):

```json
{
  "mcpServers": {
    "odoo_online": {
      "command": "python3",
      "args": [
        "/ABSOLUTE/PATH/TO/odoo_online_mcp_gateway/run_gateway.py",
        "--env-file",
        "/ABSOLUTE/PATH/TO/odoo_online_mcp_gateway/.env",
        "stdio"
      ]
    }
  }
}
```

**Config file location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**Step 3** — Fully quit and re-open Claude Desktop.

**Try these prompts:**
- *"List the Odoo models I can access."*
- *"Describe the `sale.order` model and its important fields."*
- *"Find the last 20 sales orders — show id, name, state, and amount_total."*
- *"Aggregate sales orders by state and sum the total amount."*

See the full guide: [docs/CLAUDE_DESKTOP_GUIDE.md](docs/CLAUDE_DESKTOP_GUIDE.md)

---

## Connecting to Cursor (stdio via Docker)

```json
{
  "mcpServers": {
    "odoo_online": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--env-file", "/ABSOLUTE/PATH/TO/.env",
        "odoo-online-mcp-gateway-readonly:0.1.1"
      ]
    }
  }
}
```

See the full guide: [docs/CURSOR_GUIDE.md](docs/CURSOR_GUIDE.md)

---

## HTTP Mode (for Servers / Remote Access)

For remote deployments, CI pipelines, or any HTTP-based MCP client:

```bash
# Start HTTP server (default: 127.0.0.1:8787)
python3 -m odoo_online_mcp_gateway http --host 0.0.0.0 --port 8787

# Health check endpoint
curl http://localhost:8787/healthz

# MCP endpoint
POST http://localhost:8787/mcp
  Authorization: Bearer YOUR_TOKEN
  Content-Type: application/json
```

---

## MCP Tools Reference

The gateway exposes these MCP tools to AI clients:

| Tool | Description | Default |
|------|-------------|---------|
| `list_models` | List all Odoo models allowed for your token | ✅ Enabled |
| `describe_model` | Get field metadata for any model (`fields_get`) | ✅ Enabled |
| `search_records` | Search and read records (`search_read`) with domain, fields, limit, offset, order | ✅ Enabled |
| `get_record` | Fetch a single record by ID | ✅ Enabled |
| `aggregate_records` | Group-by aggregations (`read_group`) with metrics | ✅ Enabled |
| `create_record` | Create a record | ⚠️ Off (needs `allow_ops` + `confirm=true`) |
| `update_record` | Update a record | ⚠️ Off (needs `allow_ops` + `confirm=true`) |
| `delete_record` | Delete a record | ⚠️ Off (needs `allow_ops` + `confirm=true`) |

### Default Allowed Models (Phase 1)

Out of the box, the gateway allows these Odoo models:

| Model | Description |
|-------|-------------|
| `sale.order` | Sales Orders |
| `stock.picking` | Inventory / Delivery Orders |
| `res.partner` | Customers & Contacts |
| `account.move` | Invoices & Bills |
| `crm.lead` | CRM Leads & Opportunities |

You can add any model your Odoo user has access to — see [Configuration](#configuration).

---

## Configuration

### Simple (Environment Variables)

```bash
# Required
ODOO_BASE_URL=https://yourcompany.odoo.com
ODOO_DB=yourcompany
ODOO_LOGIN=integration@yourcompany.com
ODOO_PASSWORD=your_password_or_api_key

# Auth (comma-separated tokens for HTTP; single token for stdio)
GATEWAY_TOKENS=your_long_random_token_here
GATEWAY_TOKEN=your_long_random_token_here   # for stdio clients

# Optional tuning
GATEWAY_RATE_LIMIT_PER_MINUTE=120    # default: 120
GATEWAY_MAX_PAYLOAD_KB=512           # default: 512
GATEWAY_AUDIT_ENABLED=1              # default: 1 (true)
GATEWAY_AUDIT_LOG_PATH=audit.log     # default: none (stderr only)
GATEWAY_HIDE_INTERNAL_ERRORS=1       # default: 1 (true)
GATEWAY_DEBUG=0                      # set to 1 for verbose logs
```

### Advanced (JSON Config File)

For production use with per-token policies, fine-grained model access, and field-level restrictions:

```json
{
  "tokens": [
    {
      "name": "sales-analyst",
      "token_env": "GATEWAY_TOKEN_1",
      "policy": {
        "allow_models": ["sale.order", "res.partner", "account.move"],
        "allow_ops": ["read", "aggregate"],
        "model_rules": {
          "account.move": {
            "domain": [["move_type", "in", ["out_invoice", "out_refund"]]]
          },
          "sale.order": {
            "restrict_fields": true,
            "allowed_fields": ["id", "name", "state", "amount_total", "partner_id", "date_order"]
          }
        }
      }
    }
  ],
  "limits": {
    "max_payload_kb": 512,
    "rate_limit_per_minute": 120
  },
  "audit": {
    "enabled": true,
    "log_path": "audit.log.jsonl",
    "log_payloads": false
  },
  "security": {
    "hide_internal_errors": true
  }
}
```

```bash
export GATEWAY_CONFIG=/path/to/config.json
export GATEWAY_TOKEN_1=your_long_random_token_here
```

**Policy options per token:**
- `allow_models` — which Odoo models this token can access
- `allow_ops` — operations allowed: `read`, `aggregate`, `create`, `write`, `unlink`
- `model_rules[model].domain` — auto-appended Odoo domain filter (e.g., only show customer invoices)
- `model_rules[model].restrict_fields` + `allowed_fields` — field-level access control

See the full reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

---

## Security

The gateway is designed with security as a first principle:

- **Token authentication** — every request requires a Bearer token; tokens are stored as SHA-256 hashes in memory, never in plaintext
- **Read-only by default** — write operations (`create`, `update`, `delete`) are disabled unless explicitly configured
- **Write confirmation gate** — even when enabled, writes require `confirm: true` in the tool call arguments
- **Model allowlisting** — tokens can only access models explicitly listed in their policy
- **Field-level access control** — optionally restrict which fields a token can read per model
- **Domain injection** — automatically append Odoo domain filters per token/model (e.g., limit a token to only see the current company's invoices)
- **Rate limiting** — per-token sliding window rate limiter (default: 120 req/min)
- **Payload size cap** — reject oversized requests (default: 512 KB)
- **Error redaction** — internal exceptions are never exposed to clients in production mode
- **Audit logging** — every request logged to JSONL with timestamp, status, duration, method, and tool name

---

## CLI Reference

```
odoo-online-mcp-gateway [--env-file FILE] <mode>

Modes:
  init    Generate a starter .env and config.json (run once at setup)
  check   Validate Odoo credentials and model access (smoke test)
  http    Start HTTP MCP server  [--host HOST] [--port PORT]
  stdio   Start stdio MCP server (for Claude Desktop, Cursor, etc.)
```

```bash
# One-time setup
python3 -m odoo_online_mcp_gateway init --out-dir /path/to/config

# Smoke test (always run before connecting an AI client)
python3 -m odoo_online_mcp_gateway --env-file .env check

# HTTP server
python3 -m odoo_online_mcp_gateway --env-file .env http --host 127.0.0.1 --port 8787

# stdio server
python3 -m odoo_online_mcp_gateway --env-file .env stdio
```

---

## Docker

### docker-compose (recommended)

```bash
cd docker
cp env.example .env
# Edit .env with your Odoo credentials and token
docker-compose up -d
```

### Manual Docker run

```bash
docker build -t odoo-online-mcp-gateway -f docker/Dockerfile .

docker run -d \
  --name odoo-mcp \
  -p 8787:8787 \
  -e ODOO_BASE_URL="https://yourcompany.odoo.com" \
  -e ODOO_DB="yourcompany" \
  -e ODOO_LOGIN="integration@yourcompany.com" \
  -e ODOO_PASSWORD="your_password" \
  -e GATEWAY_TOKENS="your_token_here" \
  odoo-online-mcp-gateway
```

### Health check

```bash
curl http://localhost:8787/healthz
# → ok
```

---

## Development

```bash
# Clone
git clone https://github.com/KSROlabs/odoo_online_mcp_gateway.git
cd odoo_online_mcp_gateway

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
black odoo_online_mcp_gateway/
flake8 odoo_online_mcp_gateway/
```

### Running tests

```bash
# All tests
pytest

# With coverage
pytest --cov=odoo_online_mcp_gateway --cov-report=term-missing
```

---

## Project Structure

```
odoo_online_mcp_gateway/
├── odoo_online_mcp_gateway/
│   ├── cli.py            # CLI entrypoint (init / check / http / stdio modes)
│   ├── config.py         # Settings loader (env vars + JSON config file)
│   ├── constants.py      # Shared constants (timeout, defaults)
│   ├── logging_config.py # Structured logging setup
│   ├── mcp.py            # MCP JSON-RPC 2.0 handler + tool definitions
│   ├── odoo_xmlrpc.py    # Odoo XML-RPC client with timeout + re-auth
│   ├── policy.py         # Token auth + rate limiting + scope enforcement
│   ├── server_http.py    # Threaded HTTP server (POST /mcp, GET /healthz)
│   └── server_stdio.py   # stdio transport (NDJSON + LSP framing)
├── docs/
│   ├── CLAUDE_DESKTOP_GUIDE.md   # Step-by-step for Claude Desktop
│   ├── CURSOR_GUIDE.md           # Step-by-step for Cursor
│   ├── CONFIGURATION.md          # Full configuration reference
│   └── TROUBLESHOOTING.md        # Common issues and solutions
├── docker/
│   ├── Dockerfile                # Production image
│   ├── Dockerfile.readonly       # Read-only hardened image
│   ├── docker-compose.yml        # Compose stack
│   └── config.example.json       # Example gateway config
├── tests/
│   ├── test_mcp_validation.py    # MCP handler + argument validation tests
│   ├── test_policy.py            # Auth, rate limit, scope enforcement tests
│   ├── test_stdio_transport.py   # stdio framing tests
│   └── test_integration_example.py
├── run_gateway.py                # Convenience launcher (for stdio config)
└── pyproject.toml
```

---

## Troubleshooting

**Gateway won't start — "Missing required environment variables"**
→ Make sure `ODOO_BASE_URL`, `ODOO_DB`, `ODOO_LOGIN`, `ODOO_PASSWORD` are all set.

**"Odoo authentication failed"**
→ Check your database name (Settings → About → Database), verify you can log in manually.

**"Unauthorized" (401)**
→ The Bearer token in your MCP client doesn't match `GATEWAY_TOKENS` / `GATEWAY_TOKEN`.

**"Forbidden: Model not allowed" (403)**
→ The model isn't in `allow_models` for your token. Add it to `config.json` and restart.

**"Rate limit exceeded" (429)**
→ Increase `GATEWAY_RATE_LIMIT_PER_MINUTE` or wait 60 seconds.

Full troubleshooting guide: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## FAQ

**Does this work with self-hosted Odoo (Community/Enterprise)?**
Yes. The gateway uses the standard XML-RPC API, which is available in all Odoo editions. For self-hosted Odoo you could also install a native module, but this gateway works there too.

**Does this modify anything in my Odoo instance?**
No. The gateway only reads/writes data through the existing XML-RPC API using the permissions of the integration user you configure. Nothing is installed in Odoo.

**Is it safe to use on production Odoo Online?**
Yes. By default the gateway is read-only. Use a dedicated integration user with minimal permissions. Review the [Security section](#security) for hardening options.

**Can I expose the HTTP gateway to the internet?**
You can, but add a reverse proxy (nginx/Caddy) with TLS in front of it first. The gateway itself speaks plain HTTP on port 8787.

**Can I add more Odoo models beyond the default five?**
Yes — add them to `allow_models` in `config.json` and ensure the integration user has access to those apps in Odoo.

**What Odoo versions are supported?**
The gateway uses the XML-RPC `/xmlrpc/2/` endpoint, which has been stable since Odoo 8. Tested against Odoo 16, 17, and 18 Online.

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Add tests for new functionality
4. Run `pytest` and `flake8` before submitting
5. Open a Pull Request

For bug reports and feature requests, open an issue on GitHub.

---

## Custom Development & Enterprise Support

Need a **custom integration**, additional Odoo models, a write-enabled configuration, or enterprise deployment support?

We offer:
- Custom policy configurations tailored to your Odoo setup
- Deployment to your infrastructure (Docker, Kubernetes, cloud VMs)
- Integration with additional AI clients and workflows
- Enterprise support plans

**Contact us:** [info@ksrolabs.com](mailto:info@ksrolabs.com)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## About

Built by [KSRO Labs](mailto:info@ksrolabs.com) — specialists in Odoo integrations and AI-powered business automation.

If this project saves you time, give it a ⭐ on GitHub — it helps others find it!
