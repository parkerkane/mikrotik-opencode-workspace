# MikroTik Manager — Architecture

## Overview

An OpenCode workspace for managing MikroTik routers via an MCP (Model Context Protocol) server. OpenCode communicates with the MCP server over stdio; the MCP server translates tool calls into RouterOS API sentences over a TCP socket.

```
┌─────────────────────────────────────────────────────┐
│  OpenCode (CLI / Editor)                            │
│                                                     │
│  User prompt ──► OpenCode ──► MCP tool call         │
└────────────────────────┬────────────────────────────┘
                         │ stdio (JSON-RPC 2.0)
                         ▼
┌─────────────────────────────────────────────────────┐
│  MikroTik MCP Server  (Python)                      │
│                                                     │
│  • Reads credentials from .env                      │
│  • Receives router host as CLI argument             │
│  • Encodes/decodes RouterOS API sentences           │
│  • Exposes MikroTik operations as MCP tools         │
└────────────────────────┬────────────────────────────┘
                         │ TCP 8728 / 8729
                         ▼
┌─────────────────────────────────────────────────────┐
│  MikroTik Router  (RouterOS)                        │
│                                                     │
│  Native API  →  /system/resource/print, etc.        │
└─────────────────────────────────────────────────────┘
```

## Components

### 1. MCP Server (`packages/mcp-server/`)
- Language: Python
- Transport: **stdio** (launched by OpenCode as a child process)
- Credentials: loaded from `.env` (`MIKROTIK_USER`, `MIKROTIK_PASSWORD`)
- Router host: passed as first CLI argument (`python packages/mcp-server/src/main.py <host>`)
- Router transport: RouterOS API over TCP, optionally TLS on `8729`

### 2. OpenCode Project Configuration (`opencode.json`)
- Declares the MCP server at project scope
- Wires the CLI argument (host) and inherits env vars from the shell

### 3. Environment File (`.env`)
- **Never committed** — listed in `.gitignore`
- Contains `MIKROTIK_USER` and `MIKROTIK_PASSWORD`
- May also contain API transport settings such as `MIKROTIK_API_SSL` and `MIKROTIK_TLS_VERIFY`

### 4. Test Suite (`packages/mcp-server/tests/`)
- Uses `pytest` for fast local verification
- Mocks RouterOS API socket I/O so default tests do not require a live router
- Covers sentence encoding, login flow, error handling, and MCP tool behavior separately

## Communication Protocol

The MikroTik RouterOS API is a sentence-based protocol:

- The client sends command sentences such as `/interface/print` or `/ip/address/add`
- Command arguments are sent as attribute words such as `=address=10.0.0.1/24`
- Queries are sent as query words such as `?dynamic=true` and `?#|`
- Each sentence ends with a zero-length word
- The router replies with `!re`, `!done`, `!trap`, `!empty`, or `!fatal`

Common command patterns:

| API command | Purpose |
|-------------|---------|
| `/<menu>/print` | List records, optionally with `.proplist` and queries |
| `/<menu>/getall` | Alias of `print` |
| `/<menu>/add` | Create record |
| `/<menu>/set` | Update record by `.id` |
| `/<menu>/remove` | Delete record by `.id` |
| `/<menu>/monitor` | One-shot operational command where supported |
| `/cancel` | Cancel a tagged long-running command |

Authentication is performed with `/login` over the API socket.

Default connection settings:

- Host: supplied as CLI argument
- Port: `8728` by default, `8729` when API-SSL is enabled
- TLS verification: configurable for lab environments

## Security Considerations

- Credentials live only in `.env`, never in code or config files
- `.env` is git-ignored
- Prefer `api-ssl` on port `8729` in production
- TLS verification should be enabled for production; a flag allows disabling it for lab environments
- The MCP server runs locally — it is not exposed over any network port

## Scalability

Multiple routers can be managed by launching separate MCP server instances, each with a different host argument. OpenCode supports multiple MCP servers in `opencode.json`.
