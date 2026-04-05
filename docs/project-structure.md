# Project Structure

```
manager-oc/
│
├── .env                          # Credentials (git-ignored)
├── .env.example                  # Template — safe to commit
├── .gitignore
├── .mcp.json                     # OpenCode project-scope MCP config
│
├── docs/
│   ├── architecture.md           # System architecture overview
│   ├── implementation-phases.md   # Suggested build order and milestones
│   ├── testing.md                # pytest and mocking strategy
│   ├── mcp-server-design.md      # MCP tools catalog and design
│   ├── project-structure.md      # This file
│   └── mcp-configuration.md      # How to configure OpenCode MCP
│
└── packages/
    └── mcp-server/               # The MCP server package
        ├── pyproject.toml
        ├── src/
        │   ├── main.py           # Entry point — parse args, load .env, start server
        │   ├── server.py         # MCP server setup, tool registration
        │   ├── client.py         # RouterOS API client (login, sentence transport)
        │   └── tools/
        │       ├── system.py     # system_* tools
        │       ├── interface.py  # interface_* tools
        │       ├── ip_address.py # ip_address_* tools
        │       ├── ip_route.py   # ip_route_* tools
        │       ├── dhcp.py       # dhcp_* tools
        │       ├── firewall.py   # firewall_* tools
        │       ├── dns.py        # dns_* tools
        │       ├── wireless.py   # wireless_* tools
        │       ├── backup.py     # composite backup collection tool
        │       └── diagnostics.py# tool_ping, tool_traceroute, etc.
        └── tests/
            ├── conftest.py       # Shared pytest fixtures
            ├── test_client.py    # API client behavior and error handling
            ├── test_server.py    # MCP registration and dispatch
            └── tools/
                ├── test_system.py# Per-tool behavior with mocked client
                └── test_backup.py# Composite backup workflow behavior
```

## Key Files

### `.env`
```
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=yourpassword
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=false
```

### `.env.example`
```
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=false
```

### `packages/mcp-server/src/main.py`
Entry point responsibilities:
1. Read `sys.argv[1]` for the router host (required)
2. Load `.env` from the workspace root via `python-dotenv`
3. Validate that `MIKROTIK_USER` and `MIKROTIK_PASSWORD` are set
4. Instantiate the RouterOS API client with host + credentials
5. Start the MCP server on stdio

### `packages/mcp-server/src/client.py`
RouterOS API client responsibilities:
1. Open a socket to the router on `8728` or `8729`
2. Perform `/login` with username and password
3. Encode and decode API words and sentences
4. Send commands such as `/interface/print`, `/ip/address/add`, and `/ip/address/set`
5. Parse `!re`, `!done`, `!trap`, and `!fatal` replies into typed results

## Dependencies

```json
{
  "dependencies": {
    "mcp": "^1.x",
    "python-dotenv": "^1.x"
  },
  "optional-dependencies": {
    "test": [
      "pytest>=8,<9",
      "pytest-asyncio>=0.23,<1",
      "pytest-socket>=0.7,<1"
    ]
  }
}
```

Python 3.11+ is required.

## Build

```bash
cd packages/mcp-server
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pytest
```

## gitignore entries

```
.env
packages/mcp-server/.venv/
__pycache__/
.pytest_cache/
```
