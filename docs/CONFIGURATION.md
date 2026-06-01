# Configuration Guide

This guide explains all configuration options for the Odoo Online MCP Gateway.

## Table of Contents

1. [Odoo Connection (Required)](#odoo-connection)
2. [Gateway Authentication](#gateway-authentication)
3. [Rate Limiting & Limits](#rate-limiting--limits)
4. [Audit Logging](#audit-logging)
5. [Advanced Configuration](#advanced-configuration)
6. [Troubleshooting](#troubleshooting)

---

## Odoo Connection

These environment variables tell the gateway how to connect to your Odoo Online instance.

### Required Variables

#### `ODOO_BASE_URL`
Your Odoo Online URL (without trailing slash).

```bash
export ODOO_BASE_URL="https://mycompany.odoo.com"
```

**Format**: `https://subdomain.odoo.com` (or custom domain if configured)

**How to find it**: Look at the URL in your browser when logged into Odoo.

#### `ODOO_DB`
Your database name. This is usually (but not always) the same as your subdomain.

```bash
export ODOO_DB="mycompany"
```

**How to find it**:
1. Log into Odoo
2. Go to Settings → About (or click your user menu → About)
3. Look for the "Database" field
4. Or ask your Odoo administrator

**⚠️ Important**: This is NOT the full URL, just the database name (e.g., "mycompany", not "mycompany.odoo.com").

#### `ODOO_LOGIN`
Your Odoo user email address. For security, create a dedicated integration user.

```bash
export ODOO_LOGIN="integration@mycompany.com"
```

**Best Practice**: Create a dedicated "MCP Integration" user in Odoo with:
- Type: User (not Manager/Admin)
- Access: Only the apps you need (Sales, Inventory, CRM, Invoicing)
- No other special permissions

#### `ODOO_PASSWORD`
Your password or API key.

```bash
export ODOO_PASSWORD="your_password_or_api_key"
```

**Security**: Don't hardcode this. Use environment files or secret management.

### Example Setup

```bash
#!/bin/bash
export ODOO_BASE_URL="https://acme.odoo.com"
export ODOO_DB="acme"
export ODOO_LOGIN="integration@acme.com"
export ODOO_PASSWORD="$(cat ~/.odoo_api_key)"

python3 -m odoo_online_mcp_gateway http --host 127.0.0.1 --port 8787
```

---

## Gateway Authentication

These variables control which tokens are allowed to access the gateway.

### `GATEWAY_TOKENS` (Simple Mode)

Comma-separated list of bearer tokens that clients must provide.

```bash
export GATEWAY_TOKENS="token_abc123,token_xyz789"
```

**Usage**: Clients send `Authorization: Bearer token_abc123` in HTTP requests.

**Security Tips**:
- Generate long random tokens: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- Rotate tokens periodically
- Don't commit tokens to git

**Example token generation**:
```bash
python3 << 'EOF'
import secrets
for i in range(3):
    print(f"Token {i+1}: {secrets.token_urlsafe(32)}")
EOF
```

### `GATEWAY_TOKEN` (stdio mode)

For Claude Desktop / Cursor (stdio mode), set this to one of the tokens in `GATEWAY_TOKENS`.

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python3",
      "args": ["/path/to/run_gateway.py", "stdio"],
      "env": {
        "GATEWAY_TOKEN": "token_abc123"
      }
    }
  }
}
```

### `GATEWAY_CONFIG` (Advanced Mode)

Path to a JSON configuration file. This allows fine-grained per-token policies.

```bash
export GATEWAY_CONFIG="/etc/odoo-gateway/config.json"
```

See [Advanced Configuration](#advanced-configuration) for the file format.

---

## Rate Limiting & Limits

### `GATEWAY_RATE_LIMIT_PER_MINUTE`

Maximum requests per minute per token (default: 120).

```bash
export GATEWAY_RATE_LIMIT_PER_MINUTE=200
```

**Recommendations**:
- Default (120): ~2 requests/second - Suitable for most uses
- High (500): For dashboards or heavy workloads
- Unlimited (0): `export GATEWAY_RATE_LIMIT_PER_MINUTE=0`

**Example scenario**:
- 120/min = 2/sec = reasonable for interactive use
- If AI tool gets rate-limited, increase to 300-500

### `GATEWAY_MAX_PAYLOAD_KB`

Maximum request size in kilobytes (default: 512 KB).

```bash
export GATEWAY_MAX_PAYLOAD_KB=1024
```

**When to increase**:
- If sending large search domains or batch operations
- Typical value: 512-2048 KB

**When to decrease**:
- Security hardening (prevent DoS)
- Minimum recommended: 256 KB

---

## Audit Logging

### `GATEWAY_AUDIT_ENABLED`

Enable/disable audit logging (default: true).

```bash
export GATEWAY_AUDIT_ENABLED=1
```

### `GATEWAY_AUDIT_LOG_PATH`

File where audit events are written (newline-delimited JSON).

```bash
export GATEWAY_AUDIT_LOG_PATH="/var/log/odoo-gateway/audit.log"
```

**Example audit line**:
```json
{"ts": 1711500000.123, "status": 200, "duration_ms": 45, "method": "tools/call", "tool": "search_records"}
```

### `GATEWAY_AUDIT_LOG_PAYLOADS`

Include full request/response in audit log (default: false).

```bash
export GATEWAY_AUDIT_LOG_PAYLOADS=1
```

**⚠️ Warning**: This may log sensitive data. Only enable for debugging.

---

## Error Redaction

### `GATEWAY_HIDE_INTERNAL_ERRORS`

Hide internal exceptions from MCP clients (default: true).

```bash
export GATEWAY_HIDE_INTERNAL_ERRORS=1
```

When enabled, the gateway returns a generic JSON-RPC `Internal error` without including the Python/Odoo exception string in the response.

---

## Advanced Configuration

For production deployments, use a JSON configuration file instead of env vars.

### JSON Configuration File

Create `config.json`:

```json
{
  "tokens": [
    {
      "name": "dashboard-user",
      "token_env": "TOKEN_DASHBOARD",
      "policy": {
        "allow_models": [
          "stock.picking",
          "sale.order",
          "account.move"
        ],
        "allow_ops": ["read", "aggregate"],
        "model_rules": {
          "account.move": {
            "domain": [["move_type", "in", ["out_invoice", "out_refund"]]]
          },
          "sale.order": {
            "domain": [["state", "!=", "draft"]],
            "restrict_fields": true,
            "allowed_fields": ["id", "name", "state", "amount_total"]
          }
        }
      }
    },
    {
      "name": "readonly-analyst",
      "token_env": "TOKEN_ANALYST",
      "policy": {
        "allow_models": ["res.partner", "sale.order", "account.move"],
        "allow_ops": ["read", "aggregate"]
      }
    }
  ],
  "limits": {
    "max_payload_kb": 512,
    "rate_limit_per_minute": 120
  },
  "audit": {
    "enabled": true,
    "log_path": "/var/log/gateway/audit.log",
    "log_payloads": false
  },
  "security": {
    "hide_internal_errors": true
  }
}
```

Then set:
```bash
export GATEWAY_CONFIG="/path/to/config.json"
export TOKEN_DASHBOARD="token_abc123..."
export TOKEN_ANALYST="token_xyz789..."
```

### Per-Token Model Rules

Each token can have fine-grained rules for specific models:

```json
"model_rules": {
  "account.move": {
    "domain": [["move_type", "in", ["out_invoice", "out_refund"]]],
    "restrict_fields": true,
    "allowed_fields": ["id", "number", "amount_total", "date"]
  }
}
```

**Options**:
- **domain**: Odoo domain filter applied to all queries (e.g., only show customer invoices)
- **restrict_fields**: If true, only allowed_fields can be accessed
- **allowed_fields**: List of field names that can be queried

---

## Docker Configuration

### docker-compose.yml

```yaml
services:
  gateway:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8787:8787"
    environment:
      - ODOO_BASE_URL=${ODOO_BASE_URL}
      - ODOO_DB=${ODOO_DB}
      - ODOO_LOGIN=${ODOO_LOGIN}
      - ODOO_PASSWORD=${ODOO_PASSWORD}
      - GATEWAY_CONFIG=/app/config.json
      - GATEWAY_TOKEN_1=${GATEWAY_TOKEN_1}
      - GATEWAY_AUDIT_ENABLED=1
      - GATEWAY_AUDIT_LOG_PATH=/var/log/gateway/audit.log
    volumes:
      - ./config.json:/app/config.json:ro
      - ./logs/:/var/log/gateway/
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8787/healthz', timeout=2).read()"]
      interval: 10s
      timeout: 3s
      retries: 5
      interval: 30s
      timeout: 10s
      retries: 3
```

### .env file (for docker-compose)

Create `.env`:
```bash
ODOO_BASE_URL=https://acme.odoo.com
ODOO_DB=acme
ODOO_LOGIN=integration@acme.com
ODOO_PASSWORD=your_password_here
GATEWAY_TOKEN_1=long_random_token_here
```

Then run:
```bash
docker-compose up -d
```

---

## Kubernetes Configuration

For Kubernetes, use Secrets:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: odoo-gateway-secrets
type: Opaque
stringData:
  odoo-password: "your_password"
  gateway-token: "your_token"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: odoo-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: odoo-gateway
  template:
    metadata:
      labels:
        app: odoo-gateway
    spec:
      containers:
      - name: gateway
        image: odoo-gateway:0.1.1
        ports:
        - containerPort: 8787
        env:
        - name: ODOO_BASE_URL
          value: "https://acme.odoo.com"
        - name: ODOO_DB
          value: "acme"
        - name: ODOO_LOGIN
          value: "integration@acme.com"
        - name: ODOO_PASSWORD
          valueFrom:
            secretKeyRef:
              name: odoo-gateway-secrets
              key: odoo-password
        - name: GATEWAY_TOKENS
          valueFrom:
            secretKeyRef:
              name: odoo-gateway-secrets
              key: gateway-token
        - name: GATEWAY_RATE_LIMIT_PER_MINUTE
          value: "300"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /mcp
            port: 8787
          initialDelaySeconds: 30
          periodSeconds: 10
```

---

## Troubleshooting

### Gateway won't start: "Missing required environment variables"

**Cause**: One of `ODOO_BASE_URL`, `ODOO_DB`, `ODOO_LOGIN`, `ODOO_PASSWORD` is missing.

**Fix**:
```bash
export ODOO_BASE_URL="https://your.odoo.com"
export ODOO_DB="yourdatabase"
export ODOO_LOGIN="user@example.com"
export ODOO_PASSWORD="your_password"
```

### "Odoo authentication failed" when running `check` command

**Cause**: Wrong credentials or database name.

**Fix**:
1. Verify credentials in browser (can you log in?)
2. Verify database name matches (Settings → About → Database)
3. Check user is active and not locked

### "Unauthorized" error from MCP client

**Cause**: Bearer token doesn't match GATEWAY_TOKENS.

**Fix**:
```bash
# Check what tokens are configured
echo $GATEWAY_TOKENS

# Make sure client sends matching token
# HTTP: Authorization: Bearer <token>
# stdio: GATEWAY_TOKEN env var matches
```

### "Rate limit exceeded" errors

**Cause**: Requests per minute exceeds GATEWAY_RATE_LIMIT_PER_MINUTE.

**Fix**:
```bash
export GATEWAY_RATE_LIMIT_PER_MINUTE=500  # Increase limit
```

### Docker container keeps restarting

**Cause**: Usually Odoo connection issues or missing env vars.

**Fix**:
```bash
# Check logs
docker-compose logs -f gateway

# Verify Odoo is reachable
curl https://your.odoo.com

# Verify credentials (from host)
python3 -c "
from odoo_online_mcp_gateway.odoo_xmlrpc import OdooXMLRPC
o = OdooXMLRPC('https://your.odoo.com', 'db', 'login', 'password')
print('UID:', o.authenticate())
"
```

### High memory usage

**Cause**: Large Odoo queries loading too many records.

**Fix**:
- Add `limit` to search_records calls (max 500 default)
- Use domain filters to narrow results
- Check if `restrict_fields` is needed per-token

---

## Next Steps

- See [README.md](../README.md) for setup instructions
- See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for more error scenarios
- For custom integrations or enterprise support: [info@ksrolabs.com](mailto:info@ksrolabs.com)
- GitHub Issues: https://github.com/KSROlabs/odoo_online_mcp_gateway/issues
