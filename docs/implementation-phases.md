# Implementation Phases

## Goal

Build the MikroTik MCP server in small, testable phases, starting with the narrowest useful tool and expanding only after the transport, tool contract, and test approach are proven.

## Phase 1: Foundation + `resource_print`

Start here.

Deliverables:

- Python package scaffold under `packages/mcp-server/`
- RouterOS API client with:
  - socket connect
  - `/login`
  - word/sentence encoding and decoding
  - `print(...)` helper
- MCP server bootstrap over stdio
- `resource_print` tool
- optional `jq_filter` support for `resource_print`
- pytest coverage for client encoding, reply parsing, `resource_print`, and invalid filter handling

Why this phase first:

- `resource_print` exercises the most important read path
- it validates query words, `.proplist`, and normalized JSON output
- it provides immediate utility across many RouterOS menus without implementing many dedicated tools first

Definition of done:

- can query arbitrary menus like `/interface`, `/ip/route`, `/system/resource`
- returns structured JSON
- supports optional `.proplist` and query input
- supports optional `jq_filter` after JSON normalization
- tests pass locally

## Phase 2: Generic Mutation Tools

Deliverables:

- `resource_add`
- `resource_set`
- `resource_remove`
- `command_run`

What needs to be done:

- implement add/set/remove helpers in the RouterOS API client
- validate required inputs such as menu path and `.id`
- normalize `!done`, `!empty`, and `!trap` handling for mutation commands
- add tests for successful mutation and common RouterOS failures

Why next:

- this completes the generic CRUD-style base layer
- dedicated tools can then be thin wrappers rather than reimplementing command construction

## Phase 3: Core Operational Tools

Deliverables:

- system read tools
- interface tools
- IP address tools
- IP route tools
- DHCP read tools
- DNS read/set tools

What needs to be done:

- wrap the generic client methods in user-friendly MCP tools
- add narrower input schemas and clearer descriptions
- define stable output shapes for common operational commands
- add tests per domain

Why next:

- these are the highest-value day-2 operations
- they reduce the need for users to know raw RouterOS menu paths

## Phase 4: File Handling + Backup Workflow

Deliverables:

- file listing helper
- file download helper
- `system_backup_save`
- `system_export`
- `system_backup_collect`

What needs to be done:

- define how router files are read/downloaded through the chosen implementation path
- implement local `backups/` directory handling
- generate safe, unique filenames
- handle partial failures clearly
- test router-side success and local download failure cases

Why this is separate:

- file transfer introduces different behavior than normal API command wrappers
- backup collection is a composite workflow, not a single API sentence

## Phase 5: Firewall, Bridge, VLAN, VPN

Deliverables:

- bridge and VLAN tools
- firewall filter/NAT/address-list tools
- PPP tools
- WireGuard tools

What needs to be done:

- build dedicated wrappers around the generic mutation/read layer
- add careful validation for destructive changes
- test rule ordering and id-based updates

Why later:

- these areas are more change-sensitive and easier to get wrong
- the generic base from phases 1 and 2 should exist first

## Phase 6: Streaming + Long-Running Commands

Deliverables:

- `resource_listen`
- `command_cancel`
- selected monitor or diagnostics tools where MCP UX makes sense

What needs to be done:

- design tagged command handling
- define how streaming data is exposed in MCP without creating a poor UX
- test cancellation and interrupted command handling

Why last:

- long-running commands are harder to model and test
- they depend on a solid client transport and reply correlation layer

## Cross-Cutting Work

These apply in every phase:

- keep transport logic isolated from tool logic
- add pytest coverage with mocked RouterOS replies
- keep error messages actionable
- avoid exposing destructive commands without clear parameter validation
- keep outputs JSON-shaped and stable

## Recommended Immediate Next Steps

1. Create `packages/mcp-server/` scaffold.
2. Implement low-level RouterOS API encoding/decoding.
3. Implement `/login`.
4. Implement `print(...)` in the client.
5. Implement `resource_print` with optional `jq_filter`.
6. Add tests before expanding to mutation tools.
