# Testing Strategy

## Goals

- Verify MCP tools map inputs to the correct RouterOS API commands
- Cover error handling without requiring a live router
- Keep most tests fast and deterministic by mocking API replies

## Test Stack

- `pytest` for the test runner and assertions
- `pytest-asyncio` if the server or client uses async I/O
- `unittest.mock` for patching the client layer or socket transport
- `pytest-socket` to block accidental live network access in default test runs

## Recommended Test Layout

```
tools/mikrotik/
├── mikrotik_mcp/
└── tests/
    ├── conftest.py
    ├── test_client.py
    ├── test_server.py
    └── tools/
        ├── test_system.py
        ├── test_interface.py
        └── test_firewall.py
```

## What To Mock

### 1. RouterOS API replies

Mock outbound API socket I/O in client tests so the suite does not depend on router availability, credentials, or TLS state.

Use these mocks to cover:

- Successful `!re` and `!done` reply sequences
- `!trap` and `!fatal` error replies
- Connection failures, timeouts, login failures, and TLS verification errors
- router file existence checks and download failures for backup workflows

### 2. MCP tool execution boundaries

In tool tests, mock the RouterOS client methods instead of doing real network I/O. This keeps the tests focused on:

- input validation
- request-to-client mapping
- response shaping
- surfaced error messages
- optional filtered-output behavior where supported

## Suggested Test Levels

### Unit tests

Target pure logic and thin wrappers:

- base URL construction
- login sentence construction
- word and sentence encoding
- env parsing
- RouterOS reply translation
- per-tool request mapping

### Integration-style tests

Run the MCP server locally with a mocked client or mocked socket transport and verify tool registration and response payloads.

These tests should still avoid a live router by default.

### Optional live tests

If live-router verification is needed, keep it in a separate test group and require explicit opt-in via environment variables. Do not make live tests part of the default `pytest` run.

## Example Mocking Approaches

### Mock socket transport

Use `unittest.mock` around the transport layer when you want to assert exact encoded command flow, reply sequences, and tag handling at the client layer.

### Mock the client object

Use `unittest.mock.Mock` or `AsyncMock` in tool tests when you want to verify that a tool calls `client.print(...)`, `client.add(...)`, `client.set(...)`, `client.remove(...)`, or `client.command(...)` with the expected arguments.

For composite tools such as backup collection, also mock local filesystem writes and file download helpers so the test can assert operation ordering and partial-failure behavior.

## Running Tests

```bash
pytest
```

## Recommended Dependencies

```toml
[project.optional-dependencies]
test = [
  "pytest>=8,<9",
  "pytest-asyncio>=0.23,<1",
  "pytest-socket>=0.7,<1"
]
```

## Example Assertions To Cover

- `interface_list` sends `/interface/print`
- `system_reboot` sends `/system/reboot`
- `system_backup_collect` creates both router-side files before starting downloads
- `system_backup_collect` stores both files under local `backups/`
- `resource_print` applies `jq_filter` only after JSON normalization
- invalid `jq_filter` input returns a clear error
- login failure surfaces a credential-specific error
- TLS failures mention `MIKROTIK_TLS_VERIFY=false`
- `!trap` and timeout errors return actionable messages instead of raw tracebacks
