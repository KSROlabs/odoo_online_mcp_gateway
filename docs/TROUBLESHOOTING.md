# Troubleshooting Guide

This guide helps diagnose and fix common issues with the Odoo Online MCP Gateway.

## Quick Diagnostics

### 1. Test Odoo Connection

```bash
python3 -m odoo_online_mcp_gateway check
```

This runs the gateway's built-in connectivity check:
- Verifies Odoo authentication
- Tests Phase 1 models (stock.picking, sale.order, etc.)
- Shows detailed error messages if something fails

**Success output**:
```
Authentication: OK (uid=2)
[OK] stock.picking
[OK] sale.order
[OK] res.partner
[OK] account.move
[OK] crm.lead
Result: OK
```

---

## Common Issues & Solutions

### "Odoo authentication failed"

**Error**: `PermissionError: Odoo authentication failed`

**Causes**:
1. ❌ Wrong database name
2. ❌ Wrong username/password
3. ❌ User is inactive or locked
4. ❌ Wrong base URL

**Solution**:

```bash
# 1. Verify you can log in manually
# Open https://yourcompany.odoo.com and log in with your credentials

# 2. Find correct database name
# In Odoo: Settings → About → "Database" field
# Add it to a file
echo "DATABASE_NAME" > /tmp/db_name.txt

# 3. Test in Python
python3 << 'EOF'
from odoo_online_mcp_gateway.odoo_xmlrpc import OdooXMLRPC

# Try different possibilities
possibilities = [
    ("https://yourcompany.odoo.com", "yourcompany", "user@company.com", "password"),
    ("https://yourcompany.odoo.com", "yourcompany_production", "user@company.com", "password"),
]

for url, db, login, pwd in possibilities:
    try:
        odoo = OdooXMLRPC(url, db, login, pwd)
        uid = odoo.authenticate()
        print(f"✓ SUCCESS: {url} / {db} → UID {uid}")
        break
    except Exception as e:
        print(f"✗ FAIL: {db}: {e}")
EOF
```

---

### "Unauthorized" (401 error)

**Error**: `{"error": {"code": -32001, "message": "Unauthorized"}}`

**Cause**: Bearer token doesn't match configured tokens.

**Solution for HTTP mode**:
```bash
# Verify token is set
echo $GATEWAY_TOKENS

# Test with curl
TOKEN="your_token_here"
curl -X POST "http://localhost:8787/mcp" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Should return list of tools, not 401
```

**Solution for stdio mode (Claude Desktop/Cursor)**:
```bash
# Check claude_desktop_config.json
cat ~/.claude/claude_desktop_config.json | jq '.mcpServers.odoo_saas.env'

# Should show:
# "GATEWAY_TOKEN": "your_token_here"

# Verify it matches a token in GATEWAY_TOKENS
echo $GATEWAY_TOKENS  # Should contain the same token
```

---

### "Forbidden: scope"

**Error**: `{"error": {"code": -32003, "message": "Forbidden: scope"}}`

**Meaning**: The token doesn't have permission for:
- The model you're querying, OR
- The operation (read/write/aggregate), OR
- The field you're requesting

**Solution**:

```bash
# 1. Check which models are allowed for your token
python3 << 'EOF'
import json
config = json.load(open("path/to/config.json"))
for token in config["tokens"]:
    print(f"Token: {token['name']}")
    print(f"  Models: {token['policy']['allow_models']}")
    print(f"  Ops: {token['policy']['allow_ops']}")
EOF

# 2. Check token policy from env var
python3 << 'EOF'
from odoo_online_mcp_gateway.config import PHASE1_MODELS
print("Default Phase 1 models:", PHASE1_MODELS)
EOF

# 3. If using JSON config, verify syntax
python3 -m json.tool config.json > /dev/null && echo "Valid JSON" || echo "Invalid JSON"

# 4. Restart gateway after changing config
# (settings are loaded at startup)
```

**To allow a new model**:

```json
{
  "tokens": [{
    "name": "analyst",
    "token": "...",
    "policy": {
      "allow_models": ["stock.picking", "sale.order", "purchase.order"],
      "allow_ops": ["read", "aggregate"]
    }
  }]
}
```

Restart the gateway for changes to take effect.

---

### "Rate limit exceeded"

**Error**: `{"error": {"code": -32002, "message": "Rate limit exceeded"}}`

**Cause**: Too many requests in the last 60 seconds.

**Default**: 120 requests/minute = 2 requests/second

**Solution**:

```bash
# Increase rate limit (e.g., 500 req/min)
export GATEWAY_RATE_LIMIT_PER_MINUTE=500

# Or disable rate limiting (not recommended for production)
export GATEWAY_RATE_LIMIT_PER_MINUTE=0

# Restart gateway
```

**If rate limiting is intentional**:
- Wait 60 seconds before retrying
- Optimize client to batch queries
- Use larger `limit` values to get more data per request

---

### "Invalid params"

**Error**: `{"error": {"code": -32602, "message": "Invalid params"}}`

**Cause**: Wrong argument type or missing required field.

**Solution**:

```bash
# Check your MCP tool call
# Example: search_records requires "model" argument

WRONG:
{"method": "tools/call", "params": {"name": "search_records", "arguments": {}}}
                                                              ↑ Missing "model"

CORRECT:
{"method": "tools/call", "params": {"name": "search_records", "arguments": {"model": "res.partner"}}}

# For domain filter, must be an array:
WRONG:
{"domain": "name = 'Acme'"}

CORRECT:
{"domain": [["name", "=", "Acme"]]}

# For limit/offset, must be integers:
WRONG:
{"limit": "10"}

CORRECT:
{"limit": 10}
```

---

### "Payload too large"

**Error**: `{"error": {"code": -32602, "message": "Invalid params", "data": "Payload too large"}}`

**Cause**: Request exceeds GATEWAY_MAX_PAYLOAD_KB (default 512 KB).

**Solution**:

```bash
# Increase max payload size
export GATEWAY_MAX_PAYLOAD_KB=2048

# Or reduce request size:
# - Use smaller domain filters
# - Request fewer fields
# - Use smaller batch sizes
# - Paginate results (use offset/limit)
```

---

### "Internal error" (500)

**Error**: `{"error": {"code": -32603, "message": "Internal error"}}`

**Cause**: Unexpected error in gateway or Odoo connection.

**Solution**:

1. **Check logs** (if running locally):
   ```bash
   # Run with debug logging
   GATEWAY_DEBUG=1 python3 -m odoo_online_mcp_gateway http

   # Look for full error message in stderr
   ```

2. **Check Docker logs** (if containerized):
   ```bash
   docker-compose logs -f gateway
   ```

3. **Test Odoo connectivity**:
   ```bash
   python3 -m odoo_online_mcp_gateway check
   ```

4. **Check audit log** (if enabled):
   ```bash
   tail -f audit.log
   ```

5. **Report issue with**:
   - Full error message from logs
   - Odoo version (Settings → About)
   - Gateway version
   - Which tool caused the error

---

### Gateway won't start

**Error**: `RuntimeError: Missing required environment variables`

**Cause**: One of ODOO_BASE_URL, ODOO_DB, ODOO_LOGIN, ODOO_PASSWORD is missing.

**Solution**:

```bash
# Set all four required variables
export ODOO_BASE_URL="https://yourcompany.odoo.com"
export ODOO_DB="yourcompany"
export ODOO_LOGIN="integration@yourcompany.com"
export ODOO_PASSWORD="your_password_or_api_key"

# Verify they're set
env | grep ODOO_

# Try starting again
python3 -m odoo_online_mcp_gateway http
```

---

### Gateway starts but port 8787 is already in use

**Error**: `OSError: [Errno 48] Address already in use`

**Solution**:

```bash
# Option 1: Use different port
python3 -m odoo_online_mcp_gateway http --port 8888

# Option 2: Kill existing process
lsof -i :8787
kill -9 <PID>

# Option 3: Check what's using the port
netstat -tlnp | grep 8787
```

---

### Docker container keeps crashing

**Error**: Container stops immediately after starting

**Solution**:

```bash
# 1. Check logs
docker-compose logs gateway

# 2. Verify env vars are set in .env or compose file
cat .env
docker-compose config | grep ODOO_

# 3. Test Odoo connectivity from host
python3 << 'EOF'
from odoo_online_mcp_gateway.odoo_xmlrpc import OdooXMLRPC
import os
odoo = OdooXMLRPC(
    base_url=os.getenv("ODOO_BASE_URL"),
    db=os.getenv("ODOO_DB"),
    login=os.getenv("ODOO_LOGIN"),
    password=os.getenv("ODOO_PASSWORD")
)
print("UID:", odoo.authenticate())
EOF

# 4. Rebuild image
docker-compose build --no-cache
docker-compose up -d
```

---

### Odoo models not accessible

**Error**: Running `check` command shows "[FAIL]" for some models

**Cause**: Integration user lacks access to the app for that model.

**Solution**:

1. **In Odoo**:
   - Go to Settings → Users & Companies → Users
   - Find your integration user
   - Under "Active" section, check the apps they need access to
   - For example, to access `sale.order`: enable "Sales" app
   - Save

2. **Model-to-app mapping**:
   - `sale.order`, `sale.order.line` → Sales app
   - `stock.picking`, `stock.move` → Inventory app
   - `account.move`, `account.journal` → Invoicing/Accounting app
   - `crm.lead`, `crm.opportunity` → CRM app
   - `res.partner`, `res.company` → Contacts app (usually always enabled)

3. **Test again**:
   ```bash
   python3 -m odoo_online_mcp_gateway check
   ```

---

### High latency / slow responses

**Cause**: Could be:
- Slow Odoo instance
- Large queries loading many records
- Network latency

**Solution**:

```bash
# 1. Profile a query
time curl -X POST "http://localhost:8787/mcp" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_records","arguments":{"model":"res.partner","limit":10}}}'

# 2. Optimize the query
# - Use smaller limit (10, 20, not 500)
# - Add domain filter to narrow results
# - Only request needed fields: "fields": ["id", "name"]

# 3. Check Odoo's server
# - Is Odoo responding quickly?
# - Check database size (Settings → Database Management)
```

---

### Memory usage growing

**Cause**: Accumulation of cached schemas or audit logs.

**Solution**:

```bash
# 1. Rotate audit logs
# Kill gateway, rename audit.log, restart
mv audit.log audit.log.backup
python3 -m odoo_online_mcp_gateway http

# 2. Check if restrict_fields/domain filters are set correctly
# Large unrestricted queries can load many records

# 3. Monitor memory
python3 << 'EOF'
import psutil
import os
pid = os.getpid()
p = psutil.Process(pid)
print(f"Memory: {p.memory_info().rss / 1024 / 1024:.1f} MB")
EOF
```

---

## Getting Help

If none of the above solutions work:

1. **Collect diagnostic information**:
   ```bash
   python3 -m odoo_online_mcp_gateway check 2>&1 | tee diag.txt
   echo "=== Environment ===" >> diag.txt
   env | grep -E "ODOO_|GATEWAY_" >> diag.txt
   echo "=== Gateway Version ===" >> diag.txt
   python3 -c "from odoo_online_mcp_gateway import __version__" 2>&1 >> diag.txt
   ```

2. **Include in bug report**:
   - Output from `check` command
   - Full error message from logs
   - Steps to reproduce
   - Odoo version
   - Gateway version
   - OS/environment (Docker, local, K8s, etc.)

3. **GitHub Issue**: https://github.com/KSROlabs/odoo_online_mcp_gateway/issues
4. **Email support**: info@ksrolabs.com

---

## Performance Checklist

If the gateway is slow, verify:

- [ ] Odoo instance is responsive (test in browser)
- [ ] Network latency is low (ping Odoo server)
- [ ] Queries include domain filters to narrow results
- [ ] Limit is not too high (don't fetch thousands of records)
- [ ] Only request needed fields
- [ ] Rate limiting is not triggering (check logs)
- [ ] Gateway has enough memory allocated (Docker: --memory limit)
- [ ] Audit logging is not enabled (or written to SSD, not USB drive)
