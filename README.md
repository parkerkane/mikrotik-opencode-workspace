# MikroTik Manager

MikroTik Manager is an OpenCode workspace for managing MikroTik routers through a local MCP server.

Current status: Phase 1 is implemented in `packages/mcp-server/`.

Implemented today:
- RouterOS API client over TCP/TLS
- `/login`
- RouterOS word and sentence encoding/decoding
- stdio MCP bootstrap with FastMCP
- generic `resource_print` tool
- optional `jq_filter` support for `resource_print`
- mocked pytest coverage for client and tool behavior

## Layout

- `packages/mcp-server/`: active Python package
- `packages/mcp-server/src/main.py`: MCP entry script
- `packages/mcp-server/src/mikrotik_mcp/server.py`: server wiring and `resource_print`
- `packages/mcp-server/src/mikrotik_mcp/client.py`: RouterOS transport and protocol logic
- `docs/implementation-phases.md`: delivery roadmap

## Requirements

- Python 3.11+
- RouterOS API enabled on the target router
- workspace-root `.env` with credentials

Example `.env`:

```env
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=yourpassword
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=false
```

Notes:
- `.env` is loaded from the repository root, not from `packages/mcp-server/`.
- TLS is enabled by default.
- Default port is `8729` when SSL is enabled, otherwise `8728`.

## Setup

Run all Python commands from `packages/mcp-server/` using your active `pyenv` Python:

```bash
pip install -e '.[test]'
```

## Run The MCP Server

From the repository root:

```bash
python packages/mcp-server/src/main.py <router-host>
```

The host argument is required.

## Testing

From `packages/mcp-server/`:

```bash
pytest
```

Run one focused test:

```bash
pytest tests/test_server.py -k invalid_jq_filter
```

Testing notes:
- `pytest` runs with `--disable-socket`, so default tests must stay fully mocked.
- Client transport tests use `FakeSocket` in `packages/mcp-server/tests/conftest.py`.

## Tool Surface

Phase 2 exposes these MCP tools:

- `resource_print`: generic RouterOS `/<menu>/print` access with optional `.proplist`, query words, extra attributes, and optional `jq_filter`
- `resource_add`: generic RouterOS `/<menu>/add`
- `resource_set`: generic RouterOS `/<menu>/set` with explicit `item_id`
- `resource_remove`: generic RouterOS `/<menu>/remove` with explicit `item_id`
- `command_run`: generic RouterOS command runner

`jq_filter` is applied only after RouterOS replies have been normalized into Python JSON-like data.

## Next

Phase 2 is next:

- `resource_add`
- `resource_set`
- `resource_remove`
- `command_run`

See `docs/implementation-phases.md` for the full roadmap.
