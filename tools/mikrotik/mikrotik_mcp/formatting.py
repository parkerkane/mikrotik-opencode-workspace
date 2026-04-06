# Copyright 2026 Timo Reunanen <timo@reunanen.eu>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from mcp.types import CallToolResult, TextContent


EMPTY_DISPLAY = "-"


def format_singleton_result(
    title: str,
    summary: str,
    record: dict[str, Any],
    *,
    preferred_fields: Sequence[str] = (),
) -> CallToolResult:
    lines = [summary, "", *_render_key_value_table(record, preferred_fields=preferred_fields)]
    return CallToolResult(
        content=[TextContent(type="text", text="\n".join(lines))],
        structuredContent=record,
    )


def format_list_result(
    title: str,
    items: list[dict[str, Any]],
    *,
    summary_noun: str,
    columns: Sequence[tuple[str, str]],
) -> CallToolResult:
    count = len(items)
    summary = f"{count} {summary_noun}{'' if count == 1 else 's'}"
    lines = [f"{title}: {summary}", "", *_render_table(items, columns=columns)]
    return CallToolResult(
        content=[TextContent(type="text", text="\n".join(lines))],
        structuredContent={"result": items},
    )


def format_interface_get_result(record: dict[str, Any]) -> CallToolResult:
    name = _display_value(record.get("name"))
    return format_singleton_result(
        "Interface",
        f"Interface: {name}",
        record,
        preferred_fields=("name", "type", "running", "disabled", "actual-mtu", "mac-address", "comment"),
    )


def format_interface_monitor_result(name: str, record: dict[str, Any]) -> CallToolResult:
    rx_rate = _display_value(record.get("rx-bits-per-second"))
    tx_rate = _display_value(record.get("tx-bits-per-second"))
    return format_singleton_result(
        "Interface Monitor",
        f"Interface monitor {name}: rx {rx_rate}, tx {tx_rate}",
        {"name": name, **record},
        preferred_fields=(
            "name",
            "status",
            "rx-bits-per-second",
            "tx-bits-per-second",
            "rx-packets-per-second",
            "tx-packets-per-second",
            "rx-byte",
            "tx-byte",
        ),
    )


def format_ip_address_get_result(record: dict[str, Any]) -> CallToolResult:
    address = _display_value(record.get("address"))
    return format_singleton_result(
        "IP Address",
        f"IP address: {address}",
        record,
        preferred_fields=("address", "interface", "network", "disabled", "dynamic", "comment"),
    )


def format_ip_route_get_result(record: dict[str, Any]) -> CallToolResult:
    destination = _display_value(record.get("dst-address"))
    gateway = _display_value(record.get("gateway"))
    return format_singleton_result(
        "IP Route",
        f"IP route: {destination} via {gateway}",
        record,
        preferred_fields=("dst-address", "gateway", "distance", "disabled", "active", "static", "comment"),
    )


def format_system_identity_result(record: dict[str, Any]) -> CallToolResult:
    name = _display_value(record.get("name"))
    return format_singleton_result("System Identity", f"System identity: {name}", record, preferred_fields=("name",))


def format_system_clock_result(record: dict[str, Any]) -> CallToolResult:
    date = _display_value(record.get("date"))
    time = _display_value(record.get("time"))
    return format_singleton_result(
        "System Clock",
        f"System clock: {date} {time}".strip(),
        record,
        preferred_fields=("date", "time", "time-zone-name", "gmt-offset", "time-zone-autodetect"),
    )


def format_system_resource_result(record: dict[str, Any]) -> CallToolResult:
    version = _display_value(record.get("version"))
    uptime = _display_value(record.get("uptime"))
    return format_singleton_result(
        "System Resource",
        f"System resource: RouterOS {version}, uptime {uptime}",
        record,
        preferred_fields=(
            "platform",
            "board-name",
            "version",
            "uptime",
            "cpu-load",
            "free-memory",
            "total-memory",
            "free-hdd-space",
            "total-hdd-space",
        ),
    )


def format_dns_get_result(record: dict[str, Any]) -> CallToolResult:
    servers = _display_value(record.get("servers"))
    remote_requests = _display_value(record.get("allow-remote-requests"))
    return format_singleton_result(
        "DNS Settings",
        f"DNS settings: servers {servers}, remote requests {remote_requests}",
        record,
        preferred_fields=("servers", "allow-remote-requests", "cache-size", "dynamic-servers", "use-doh-server"),
    )


def format_dns_resolve_result(record: dict[str, Any]) -> CallToolResult:
    name = _display_value(record.get("name"))
    address = _display_value(record.get("address"))
    return format_singleton_result(
        "DNS Resolve",
        f"DNS resolve: {name} -> {address}",
        record,
        preferred_fields=("name", "address", "server"),
    )


def format_healthcheck_result(record: dict[str, Any]) -> CallToolResult:
    api = record.get("api") if isinstance(record.get("api"), dict) else {}
    scp = record.get("scp") if isinstance(record.get("scp"), dict) else {}
    identity = api.get("identity") if isinstance(api.get("identity"), dict) else {}
    config = record.get("config") if isinstance(record.get("config"), dict) else {}
    scp_probe = scp.get("probe") if isinstance(scp.get("probe"), dict) else {}

    display_record = {
        "success": record.get("success"),
        "status": record.get("status"),
        "timestamp": record.get("timestamp"),
        "target-host": record.get("target_host"),
        "api-status": api.get("status") or ("ok" if api.get("ok") else "failed"),
        "api-code": api.get("code"),
        "api-message": api.get("message"),
        "api-name": identity.get("name"),
        "api-host": api.get("host"),
        "api-port": api.get("port"),
        "api-tls": api.get("tls"),
        "api-duration-ms": api.get("duration_ms"),
        "scp-status": scp.get("status") or ("ok" if scp.get("ok") else "failed"),
        "scp-code": scp.get("code"),
        "scp-message": scp.get("message"),
        "scp-host": scp.get("host"),
        "scp-port": scp.get("port"),
        "scp-duration-ms": scp.get("duration_ms"),
        "scp-probe": scp_probe.get("operation"),
        "scp-working-directory": scp_probe.get("working_directory"),
        "scp-listing-count": scp_probe.get("listing_count"),
        "config-api-credentials": config.get("api_credentials_configured"),
        "config-scp-credentials": config.get("scp_credentials_configured"),
        "config-scp-host-override": config.get("scp_host_override"),
        "config-resolved-scp-host": config.get("resolved_host"),
    }
    lines = [
        f"Healthcheck: {_display_value(record.get('status'))}",
        "",
        *_render_key_value_table(
            display_record,
            preferred_fields=(
                "success",
                "status",
                "timestamp",
                "target-host",
                "api-status",
                "api-code",
                "api-message",
                "api-name",
                "api-host",
                "api-port",
                "api-tls",
                "api-duration-ms",
                "scp-status",
                "scp-code",
                "scp-message",
                "scp-host",
                "scp-port",
                "scp-duration-ms",
                "scp-probe",
                "scp-working-directory",
                "scp-listing-count",
                "config-api-credentials",
                "config-scp-credentials",
                "config-scp-host-override",
                "config-resolved-scp-host",
            ),
        ),
    ]
    return CallToolResult(
        content=[TextContent(type="text", text="\n".join(lines))],
        structuredContent=record,
    )


def format_tool_ping_result(address: str, items: list[dict[str, Any]]) -> CallToolResult:
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text="\n".join(
                    [
                        f"Ping {address}: {len(items)} probe{'' if len(items) == 1 else 's'}",
                        "",
                        *_render_table(
                            items,
                            columns=(
                                ("seq", "Seq"),
                                ("host", "Host"),
                                ("size", "Size"),
                                ("ttl", "TTL"),
                                ("time", "Time"),
                                ("status", "Status"),
                            ),
                        ),
                    ]
                ),
            )
        ],
        structuredContent={"address": address, "result": items},
    )


def format_tool_traceroute_result(address: str, items: list[dict[str, Any]]) -> CallToolResult:
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text="\n".join(
                    [
                        f"Traceroute {address}: {len(items)} hop{'' if len(items) == 1 else 's'}",
                        "",
                        *_render_table(
                            items,
                            columns=(
                                ("hop", "Hop"),
                                ("host", "Host"),
                                ("address", "Address"),
                                ("loss", "Loss"),
                                ("last", "Last"),
                                ("avg", "Avg"),
                                ("best", "Best"),
                                ("worst", "Worst"),
                                ("status", "Status"),
                            ),
                        ),
                    ]
                ),
            )
        ],
        structuredContent={"address": address, "result": items},
    )


def format_interface_list_result(items: list[dict[str, Any]]) -> CallToolResult:
    return format_list_result(
        "Interfaces",
        items,
        summary_noun="interface",
        columns=(
            ("name", "Name"),
            ("type", "Type"),
            ("running", "Running"),
            ("disabled", "Disabled"),
            ("actual-mtu", "MTU"),
            ("mac-address", "MAC Address"),
        ),
    )


def format_ip_address_list_result(items: list[dict[str, Any]]) -> CallToolResult:
    return format_list_result(
        "IP Addresses",
        items,
        summary_noun="IP address",
        columns=(
            ("address", "Address"),
            ("interface", "Interface"),
            ("network", "Network"),
            ("disabled", "Disabled"),
            ("dynamic", "Dynamic"),
        ),
    )


def format_ip_route_list_result(items: list[dict[str, Any]]) -> CallToolResult:
    return format_list_result(
        "IP Routes",
        items,
        summary_noun="IP route",
        columns=(
            ("dst-address", "Destination"),
            ("gateway", "Gateway"),
            ("distance", "Distance"),
            ("active", "Active"),
            ("static", "Static"),
            ("disabled", "Disabled"),
        ),
    )


def format_dhcp_lease_list_result(items: list[dict[str, Any]]) -> CallToolResult:
    return format_list_result(
        "DHCP Leases",
        items,
        summary_noun="DHCP lease",
        columns=(
            ("address", "Address"),
            ("mac-address", "MAC Address"),
            ("host-name", "Host Name"),
            ("status", "Status"),
            ("server", "Server"),
            ("expires-after", "Expires After"),
        ),
    )


def format_dhcp_server_list_result(items: list[dict[str, Any]]) -> CallToolResult:
    return format_list_result(
        "DHCP Servers",
        items,
        summary_noun="DHCP server",
        columns=(
            ("name", "Name"),
            ("interface", "Interface"),
            ("address-pool", "Address Pool"),
            ("lease-time", "Lease Time"),
            ("disabled", "Disabled"),
        ),
    )


def format_dhcp_network_list_result(items: list[dict[str, Any]]) -> CallToolResult:
    return format_list_result(
        "DHCP Networks",
        items,
        summary_noun="DHCP network",
        columns=(
            ("address", "Address"),
            ("gateway", "Gateway"),
            ("dns-server", "DNS Server"),
            ("domain", "Domain"),
            ("ntp-server", "NTP Server"),
        ),
    )


def _render_key_value_table(record: dict[str, Any], *, preferred_fields: Sequence[str]) -> list[str]:
    ordered_fields = list(preferred_fields)
    ordered_fields.extend(key for key in sorted(record) if key not in preferred_fields)
    rows = [(field, _display_value(record.get(field))) for field in ordered_fields if field in record]
    return _render_markdown_table(("Field", "Value"), rows)


def _render_table(items: list[dict[str, Any]], *, columns: Sequence[tuple[str, str]]) -> list[str]:
    headers = tuple(label for _, label in columns)
    rows = [tuple(_display_value(item.get(field)) for field, _ in columns) for item in items]
    return _render_markdown_table(headers, rows)


def _render_markdown_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_escape_table_cell(value) for value in row) + " |")
    if len(lines) == 2:
        lines.append("| " + " | ".join(EMPTY_DISPLAY for _ in headers) + " |")
    return lines


def _display_value(value: Any) -> str:
    if value is None:
        return EMPTY_DISPLAY
    if isinstance(value, bool):
        return "yes" if value else "no"

    text = str(value).strip()
    if not text:
        return EMPTY_DISPLAY

    normalized = text.lower()
    if normalized == "true":
        return "yes"
    if normalized == "false":
        return "no"
    return text


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
