# AGENTS

## Scope
- The only active code package is `tools/mikrotik/`.

## Working Directory
- Run Python install and test commands from the repo root.

## Memory
- Store durable shared project context in `MEMORY.md`.
- Store local-only or non-shareable notes in `MEMORY.local.md`.
- Update `MEMORY.md` when new long-lived conventions, preferences, or operational notes are established.
- Keep memory entries brief and factual.
- Do not store secrets, temporary task notes, or chat-only context in either memory file.
- Shared project facts such as entry points, runtime notes, operations, and testing conventions live in `MEMORY.md`.

## Verified Commands
- Install runtime + test deps: `pip install -r requirements.txt`
- Run full test suite: `pytest`
- Run one focused test: `pytest tools/mikrotik/tests/test_server.py -k invalid_jq_filter`

## Router-First Checks
- For requests about current router state, prefer querying the live router through MCP tools first when feasible instead of answering from code, docs, or assumptions.
- This also applies before most router changes: inspect the current state first when it helps confirm targets, existing config, or safety.
- In this project, short operational prompts like `list files`, `list users`, `show interfaces`, or `check routes` should default to router state, not workspace or repository state, unless the user clearly asks about local files or code.
- Examples: list users, router files, interfaces, addresses, routes, DHCP leases, firewall rules, active sessions, and current health or status.
- For codebase or implementation questions, inspect the repository instead of the router.
- If a request is ambiguous between router state and local workspace state, prefer the router interpretation first and briefly clarify only when needed.
- If live router access is unavailable, say so explicitly before falling back to indirect evidence such as code, config, or documentation.

## Response Formatting
- Default to human-friendly Markdown when presenting router data.
- Use Markdown tables for tabular RouterOS results like users, interfaces, addresses, and routes.
- Use short summaries for single-record outputs like `/system/resource` unless the user asks for more detail.
- Only show raw JSON or raw tool output when the user explicitly requests raw data.

## Near-Term Direction
- Operational command wrappers are now in place; next work should be driven by user demand for additional diagnostics or higher-level workflows.
