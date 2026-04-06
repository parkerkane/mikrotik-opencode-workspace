# AGENTS

## Scope
- The only active code package is `packages/mcp-server/`. There is no root build/test manifest.
- Current implementation scope is through Phase 3: generic read/mutation tools plus core operational read tools and DNS set support. Roadmap source: `docs/implementation-phases.md`.

## Working Directory
- Run Python install and test commands from `packages/mcp-server/`, not the repo root.

## Verified Commands
- Install package + test deps: `pip install -e '.[test]'`
- Run full test suite: `pytest`
- Run one focused test: `pytest tests/test_server.py -k invalid_jq_filter`

## Entry Points
- OpenCode/MCP entry script: `packages/mcp-server/src/main.py`
- Real server wiring lives in `packages/mcp-server/src/mikrotik_mcp/server.py`
- RouterOS protocol/client logic lives in `packages/mcp-server/src/mikrotik_mcp/client.py`
- Top-level `src/main.py`, `src/server.py`, and `src/client.py` are thin compatibility wrappers.

## Runtime Gotchas
- `main.py` requires the router host as CLI arg: `python packages/mcp-server/src/main.py <host>`.
- Startup loads `.env` from the workspace root, not from `packages/mcp-server/`.
- Required env vars: `MIKROTIK_USER`, `MIKROTIK_PASSWORD`.
- Optional transport env vars already wired: `MIKROTIK_API_SSL`, `MIKROTIK_API_PORT`, `MIKROTIK_TLS_VERIFY`.
- TLS defaults to enabled; default port is `8729` when SSL is on, else `8728`.

## Response Formatting
- Default to human-friendly Markdown when presenting router data.
- Use Markdown tables for tabular RouterOS results like users, interfaces, addresses, and routes.
- Use short summaries for single-record outputs like `/system/resource` unless the user asks for more detail.
- Only show raw JSON or raw tool output when the user explicitly requests raw data.

## Testing Conventions
- `pytest` is configured with `--disable-socket` in `packages/mcp-server/pyproject.toml`; default tests must stay fully mocked.
- Existing tests use `FakeSocket` in `packages/mcp-server/tests/conftest.py` for client transport tests and `Mock()` for tool-layer tests.
- Keep `jq_filter` behavior tool-side: `resource_print` applies it after RouterOS replies are normalized to JSON-like Python data.

## Near-Term Direction
- If continuing feature work, Phase 4 is next: file handling, backups, exports, and backup collection workflow.
