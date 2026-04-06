# Implementation Phases

## Goal

Build the MikroTik MCP server in small, testable phases, starting with the narrowest useful tool and expanding only after the transport, tool contract, and test approach are proven.

## Phase 1: Foundation + `resource_print`

Status: done.

Deliverables:

- Python package scaffold under `tools/mikrotik-mcp/`
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

Status: done.

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

Status: done.

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

Status: done.

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

Status: done.

Deliverables:

- bridge and VLAN tools
- firewall filter/NAT/address-list tools
- PPP tools
- WireGuard tools

What was done:

- build dedicated wrappers around the generic mutation/read layer
- add careful validation for destructive changes
- test rule ordering and id-based updates

Definition of done:

- bridge, bridge port, bridge VLAN, and VLAN tools are registered in the MCP server
- firewall filter, NAT, address-list, and rule move tools are available with explicit destructive-action validation
- PPP and WireGuard wrappers are available with minimal required-field validation for add operations
- mocked pytest coverage passes locally

Why later:

- these areas are more change-sensitive and easier to get wrong
- the generic base from phases 1 and 2 should exist first

## Phase 6: Streaming + Long-Running Commands

Status: done.

Deliverables:

- `resource_listen`
- `command_cancel`
- selected monitor or diagnostics tools where MCP UX makes sense

What was done:

- implement bounded tagged `listen` support with automatic cancellation after `max_events`
- isolate bounded long-running operations onto short-lived cloned RouterOS connections so they do not interfere with the shared MCP session socket
- keep `command_cancel` available as the low-level cancel primitive while deferring true cross-call session management
- add a first dedicated diagnostics wrapper with `tool_ping`
- add tests for generated tags, cancellation, cancel fatal handling, and isolated client lifecycle

Definition of done:

- `resource_listen` returns a bounded event batch with stable metadata fields
- tagged long-running operations do not reuse the shared always-open MCP socket
- `tool_ping` is available as a safe bounded diagnostics wrapper
- mocked pytest coverage passes locally

Why last:

- long-running commands are harder to model and test
- they depend on a solid client transport and reply correlation layer

## Phase 7: Response Formatting Tightening

Status: done.

Deliverables:

- explicit presentation templates for common operational outputs
- consistent Markdown table columns per tool family
- stable handling for empty values and boolean-like fields in user-facing responses
- concise summary lines for list-style operational outputs

What was done:

- add explicit Markdown presentation templates for common operational singleton outputs such as system identity, clock, resource, and DNS settings
- define fixed default columns for list tools such as interfaces, addresses, routes, DHCP leases, DHCP servers, and DHCP networks
- standardize user-facing rendering for missing values and boolean-like status fields
- keep formatted text output paired with stable structured content, while preserving raw JSON output for generic tools such as `resource_print`

Definition of done:

- singleton operational tools return concise summary lines plus Markdown key/value tables
- list-oriented operational tools return concise count summaries plus consistent Markdown tables
- empty values and boolean-like fields render consistently in user-facing responses
- mocked pytest coverage passes locally for the formatted output paths

Why separate:

- this is a UX and presentation concern, not a RouterOS transport or MCP contract change
- it should remain easy to improve iteratively without destabilizing tool behavior or tests

## Phase 8: Operational Command Wrappers

Status: done.

Deliverables:

- dedicated wrappers for high-value operational commands such as ping, traceroute, and selected diagnostics
- narrower input schemas than generic `command_run`
- stable output shapes for common command results

What was done:

- keep `tool_ping` as the bounded per-probe wrapper and align it with the formatted operational output style
- add a dedicated `tool_traceroute` wrapper with constrained parameters and normalized hop results
- add a dedicated `dns_resolve` wrapper that normalizes RouterOS resolve replies into a stable single-record shape
- add mocked tests for success, empty responses, validation failures, and RouterOS error cases across the new wrappers

Why separate:

- generic command execution already exists, so this phase is about usability and safer schemas rather than raw capability
- operational commands have command-specific inputs and outputs that are easier to consume through dedicated wrappers

## Cross-Cutting Work

These apply in every phase:

- keep transport logic isolated from tool logic
- add pytest coverage with mocked RouterOS replies
- keep error messages actionable
- avoid exposing destructive commands without clear parameter validation
- keep outputs JSON-shaped and stable

## Recommended Immediate Next Steps

1. Add additional operational wrappers only where there is clear user demand, such as interface monitoring or selected live diagnostics.
2. Keep new command wrappers narrowly scoped with stable output shapes and mocked tests.
3. Continue improving presentation templates where operational command outputs benefit from clearer Markdown summaries or tables.
