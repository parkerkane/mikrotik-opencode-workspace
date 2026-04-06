# AGENTS

## Scope
- The only active code package is `tools/mikrotik-mcp/`.
- Current implementation scope is through Phase 8: generic read/mutation tools, core operational read tools, DNS set support, router file download, backup collection workflow, bridge/VLAN/firewall/PPP/WireGuard tooling, long-running command support, response formatting tightening, and dedicated operational command wrappers including ping, traceroute, and DNS resolve. Roadmap source: `docs/implementation-phases.md`.

## Working Directory
- Run Python install and test commands from the repo root.

## Verified Commands
- Install runtime + test deps: `pip install -r requirements.txt`
- Run full test suite: `pytest`
- Run one focused test: `pytest tools/mikrotik-mcp/tests/test_server.py -k invalid_jq_filter`

## Entry Points
- OpenCode/MCP entry script: `tools/mikrotik-mcp/src/main.py`
- Real server wiring lives in `tools/mikrotik-mcp/src/mikrotik_mcp/server.py`
- RouterOS protocol/client logic lives in `tools/mikrotik-mcp/src/mikrotik_mcp/client.py`
- Top-level `src/main.py`, `src/server.py`, and `src/client.py` are thin compatibility wrappers.

## Runtime Gotchas
- `main.py` requires the router host as CLI arg: `python tools/mikrotik-mcp/src/main.py <host>`.
- Startup loads `.env` from the workspace root.
- Required env vars: `MIKROTIK_USER`, `MIKROTIK_PASSWORD`.
- Optional transport env vars already wired: `MIKROTIK_API_SSL`, `MIKROTIK_API_PORT`, `MIKROTIK_TLS_VERIFY`.
- TLS defaults to enabled; default port is `8729` when SSL is on, else `8728`.

## Operational Shortcuts
- If the user asks to "create backup" or "create and download backup", treat that as `system_backup_collect` with `name_prefix="backup"` unless the user specifies a different prefix.
- Default local backup destination for that shortcut should be workspace-root `backups/`.

## Response Formatting
- Default to human-friendly Markdown when presenting router data.
- Use Markdown tables for tabular RouterOS results like users, interfaces, addresses, and routes.
- Use short summaries for single-record outputs like `/system/resource` unless the user asks for more detail.
- Only show raw JSON or raw tool output when the user explicitly requests raw data.

## Testing Conventions
- `pytest` is configured with `--disable-socket` in root `pytest.ini`; default tests must stay fully mocked.
- Existing tests use `FakeSocket` in `tools/mikrotik-mcp/tests/conftest.py` for client transport tests and `Mock()` for tool-layer tests.
- Keep `jq_filter` behavior tool-side: `resource_print` applies it after RouterOS replies are normalized to JSON-like Python data.

## Near-Term Direction
- Operational command wrappers are now in place; next work should be driven by user demand for additional diagnostics or higher-level workflows.
