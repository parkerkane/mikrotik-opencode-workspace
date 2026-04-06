# AGENTS

## Scope
- The only active code package is `tools/mikrotik/`.
- Current implementation scope includes generic read/mutation tools, core operational read tools, DNS set support, router file download, backup collection workflow, bridge/VLAN/firewall/PPP/WireGuard tooling, long-running command support, response formatting tightening, and dedicated operational command wrappers including ping, traceroute, and DNS resolve.

## Working Directory
- Run Python install and test commands from the repo root.

## Verified Commands
- Install runtime + test deps: `pip install -r requirements.txt`
- Run full test suite: `pytest`
- Run one focused test: `pytest tools/mikrotik/tests/test_server.py -k invalid_jq_filter`

## Entry Points
- OpenCode/MCP entry script: `tools/mikrotik/main.py`
- Real server wiring lives in `tools/mikrotik/mikrotik_mcp/server.py`
- RouterOS protocol/client logic lives in `tools/mikrotik/mikrotik_mcp/client.py`

## Runtime Gotchas
- `main.py` requires the router host as CLI arg: `python tools/mikrotik/main.py <host>`.
- Startup loads `.env` from the workspace root.
- Required env vars: `MIKROTIK_USER`, `MIKROTIK_PASSWORD`.
- Optional transport env vars already wired: `MIKROTIK_API_SSL`, `MIKROTIK_API_PORT`, `MIKROTIK_TLS_VERIFY`.
- TLS defaults to enabled; default port is `8729` when SSL is on, else `8728`.

## Operational Shortcuts
- If the user asks to "create backup" or "create and download backup", treat that as `system_backup_collect` with `name_prefix="backup"` unless the user specifies a different prefix.
- Default local backup destination for that shortcut should be workspace-root `backups/`.
- Default local destination for downloaded router files should be workspace-root `exports/`, except backup artifacts which should continue to use `backups/`.

## RouterOS Notes
- `www-ssl` requires an explicit certificate binding; a valid certificate in the store is not enough for browser HTTPS until `/ip/service www-ssl` points at it.
- Dynamic `/ip/service` entries with `connection=true` are active client sessions, not separately configurable services.
- RouterOS may reject signing a second certificate with the same subject/SAN set while another matching certificate already exists; renaming the active certificate is often the minimal safe fix.

## Response Formatting
- Default to human-friendly Markdown when presenting router data.
- Use Markdown tables for tabular RouterOS results like users, interfaces, addresses, and routes.
- Use short summaries for single-record outputs like `/system/resource` unless the user asks for more detail.
- Only show raw JSON or raw tool output when the user explicitly requests raw data.

## Testing Conventions
- `pytest` is configured with `--disable-socket` in root `pytest.ini`; default tests must stay fully mocked.
- Existing tests use `FakeSocket` in `tools/mikrotik/tests/conftest.py` for client transport tests and `Mock()` for tool-layer tests.
- Keep `jq_filter` behavior tool-side: `resource_print` applies it after RouterOS replies are normalized to JSON-like Python data.

## Near-Term Direction
- Operational command wrappers are now in place; next work should be driven by user demand for additional diagnostics or higher-level workflows.
