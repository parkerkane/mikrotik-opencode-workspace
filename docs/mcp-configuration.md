# OpenCode MCP Configuration

## Project-scope MCP config: `.mcp.json`

Placed at the workspace root, `.mcp.json` is picked up automatically by OpenCode for this project only.

```json
{
  "mcpServers": {
    "mikrotik": {
      "type": "stdio",
      "command": "python",
      "args": [
        "packages/mcp-server/src/main.py",
        "192.168.88.1"
      ],
      "env": {
        "MIKROTIK_USER": "${MIKROTIK_USER}",
        "MIKROTIK_PASSWORD": "${MIKROTIK_PASSWORD}",
        "MIKROTIK_API_SSL": "${MIKROTIK_API_SSL}",
        "MIKROTIK_API_PORT": "${MIKROTIK_API_PORT}",
        "MIKROTIK_TLS_VERIFY": "${MIKROTIK_TLS_VERIFY}"
      }
    }
  }
}
```

### Key points

- **`type: "stdio"`** — OpenCode spawns the Python process and communicates over stdin/stdout.
- **`args[1]`** — the router host (`192.168.88.1` above). Change this to target a different router without touching credentials.
- **`env`** — the API credentials and transport vars are forwarded from the shell environment. Populate them via `.env` before starting OpenCode, or export them in your shell profile.

### Passing credentials via `.env`

The MCP server itself loads `.env` from the workspace root on startup, so credentials are available even if you don't export them in your shell:

```
# .env  (workspace root, git-ignored)
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=yourpassword
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=false
```

> The `env` block in `.mcp.json` is a belt-and-suspenders approach: values come from the shell if exported, and from `.env` if not. The MCP server's startup code handles the `.env` fallback directly.

## Managing multiple routers

Add additional server entries with different names and hosts:

```json
{
  "mcpServers": {
    "mikrotik-core": {
      "type": "stdio",
      "command": "python",
      "args": ["packages/mcp-server/src/main.py", "10.0.0.1"],
      "env": {
        "MIKROTIK_USER": "${MIKROTIK_USER}",
        "MIKROTIK_PASSWORD": "${MIKROTIK_PASSWORD}",
        "MIKROTIK_API_SSL": "${MIKROTIK_API_SSL}",
        "MIKROTIK_API_PORT": "${MIKROTIK_API_PORT}",
        "MIKROTIK_TLS_VERIFY": "${MIKROTIK_TLS_VERIFY}"
      }
    },
    "mikrotik-branch": {
      "type": "stdio",
      "command": "python",
      "args": ["packages/mcp-server/src/main.py", "10.1.0.1"],
      "env": {
        "MIKROTIK_USER": "${MIKROTIK_USER}",
        "MIKROTIK_PASSWORD": "${MIKROTIK_PASSWORD}",
        "MIKROTIK_API_SSL": "${MIKROTIK_API_SSL}",
        "MIKROTIK_API_PORT": "${MIKROTIK_API_PORT}",
        "MIKROTIK_TLS_VERIFY": "${MIKROTIK_TLS_VERIFY}"
      }
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
- For self-signed certificates, set `MIKROTIK_TLS_VERIFY=false`
