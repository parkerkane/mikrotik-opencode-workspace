# OpenCode MCP Configuration

## Project-scope MCP config: `opencode.json`

Placed at the workspace root, `opencode.json` is picked up automatically by OpenCode for this project only.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "mikrotik": {
      "type": "local",
      "command": [
        "python",
        "tools/mikrotik/main.py",
        "192.168.88.1"
      ],
      "enabled": true
    }
  }
}
```

### Key points

- **`type: "local"`** — OpenCode spawns the Python process locally and communicates over stdin/stdout.
- **`command[2]`** — the router host (`192.168.88.1` above). Change this to target a different router without touching credentials.
- **No `environment` block is required** — this MCP server already loads `.env` from the workspace root on startup.

### Passing credentials via `.env`

The MCP server itself loads `.env` from the workspace root on startup, so credentials are available even if you don't export them in your shell:

```
# Static password mode
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=yourpassword
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=true
```

```env
# Passwordless startup rotation mode
MIKROTIK_USER=admin
MIKROTIK_API_PASSWORDLESS_ENABLED=true
MIKROTIK_API_PASSWORDLESS_LENGTH=32
MIKROTIK_SCP_USER=admin
MIKROTIK_SCP_PRIVATE_KEY=certs/router-key
MIKROTIK_SCP_KEY_PASSPHRASE=
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=true
```

> This server loads `.env` itself on startup, so duplicating `MIKROTIK_*` values in `opencode.json` is unnecessary.

For passwordless startup rotation details and the related `.env` settings, see `docs/passwordless-startup.md`.

## Managing multiple routers

Add additional server entries with different names and hosts:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "mikrotik-core": {
      "type": "local",
      "command": ["python", "tools/mikrotik/main.py", "10.0.0.1"],
      "enabled": true
    },
    "mikrotik-branch": {
      "type": "local",
      "command": ["python", "tools/mikrotik/main.py", "10.1.0.1"],
      "enabled": true
    }
  }
}
```

OpenCode will see tools namespaced by server name (e.g. `mikrotik-core__interface_list`).

## Verifying the MCP server is running

In OpenCode, run:

```
/mcp
```

This lists all configured MCP servers and their connection status. The `mikrotik` server should show as **connected** with the tool list populated.

## RouterOS API prerequisite

The API service must be enabled on the router. In RouterOS:

```
/ip service enable api-ssl
# or api for plain TCP (not recommended)
```

Recommended defaults:

- Use `api-ssl` on port `8729`
- Set `MIKROTIK_API_SSL=true`
- Set `MIKROTIK_API_PORT=8729`
- Keep `MIKROTIK_TLS_VERIFY=true` when your local `certs/` trust store contains the router CA
- For self-signed lab certificates without a trusted local CA, set `MIKROTIK_TLS_VERIFY=false`
