# Project Structure

```
mikrotik-manager/
│
├── .env                          # Credentials (git-ignored)
├── .env.example                  # Template — safe to commit
├── .gitignore
├── opencode.json                 # OpenCode project-scope config, including MCP
│
├── docs/
│   ├── architecture.md           # System architecture overview
│   ├── testing.md                # pytest and mocking strategy
│   ├── mcp-server-design.md      # MCP tools catalog and design
│   ├── project-structure.md      # This file
│   ├── mcp-configuration.md      # How to configure OpenCode MCP
│   └── passwordless-startup.md   # SSH key-based startup password rotation
│
├── requirements.txt              # Runtime and test dependencies
├── pytest.ini                    # Root pytest configuration
└── tools/
    └── mikrotik/                 # The MCP server project
        ├── main.py               # Entry point — parse args, load .env, start server
        ├── mikrotik_mcp/
        │   ├── server.py         # MCP server setup, tool registration
        │   ├── client.py         # RouterOS API client (login, sentence transport)
        │   ├── app.py            # FastMCP app and tool registration
        │   └── tool_impls/       # Tool implementation modules
        └── tests/
            ├── conftest.py       # Shared pytest fixtures
            ├── test_client.py    # API client behavior and error handling
            └── test_server.py    # MCP registration and dispatch
```

## Key Files

### `.env`
```
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=yourpassword
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=true
```

Passwordless startup rotation can replace `MIKROTIK_PASSWORD` with `MIKROTIK_API_PASSWORDLESS_ENABLED=true` and `MIKROTIK_SCP_PRIVATE_KEY=certs/router-key`. See `docs/passwordless-startup.md`.

### `.env.example`
```
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=
MIKROTIK_API_PASSWORDLESS_ENABLED=false
MIKROTIK_API_PASSWORDLESS_LENGTH=32
MIKROTIK_API_SSL=true
MIKROTIK_API_PORT=8729
MIKROTIK_TLS_VERIFY=true
```

### `tools/mikrotik/main.py`
Entry point responsibilities:
1. Read `sys.argv[1]` for the router host (required)
2. Load `.env` from the workspace root via `python-dotenv`
3. Validate startup auth settings for either static password mode or passwordless startup rotation
4. Instantiate the RouterOS API client with host + resolved credentials
5. Start the MCP server on stdio

### `tools/mikrotik/mikrotik_mcp/client.py`
RouterOS API client responsibilities:
1. Open a socket to the router on `8728` or `8729`
2. Perform `/login` with username and password
3. Encode and decode API words and sentences
4. Send commands such as `/interface/print`, `/ip/address/add`, and `/ip/address/set`
5. Parse `!re`, `!done`, `!trap`, and `!fatal` replies into typed results

## Dependencies

```txt
jq>=1,<2
mcp>=1,<2
python-dotenv>=1,<2
pytest>=8,<9
pytest-asyncio>=0.23,<1
pytest-socket>=0.7,<1
```

Python 3.11+ is required.

## Build

```bash
pip install -r requirements.txt
pytest
```

## gitignore entries

```
.env
__pycache__/
.pytest_cache/
```
