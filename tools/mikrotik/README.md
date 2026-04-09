# mikrotik-mcp

`mikrotik-mcp` is an MCP server for managing MikroTik routers through the RouterOS API.

## Install

From this repository root:

```bash
pip install -e tools/mikrotik
```

Directly from GitHub:

```bash
pip install "git+https://github.com/parkerkane/mikrotik-manager.git#subdirectory=tools/mikrotik"
```

## Run

```bash
python -m mikrotik_mcp <router-host>
```

Or use the console script:

```bash
mikrotik-mcp <router-host>
```

Runtime configuration comes from `MIKROTIK_*` environment variables. OpenCode `environment` entries are the primary configuration source. A local `.env` file in the current working directory is supported as a fallback for manual runs.
