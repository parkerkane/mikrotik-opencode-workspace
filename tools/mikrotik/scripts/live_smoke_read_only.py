#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mikrotik_mcp.runtime import load_settings
from mikrotik_mcp.server import (
    bridge_list_impl,
    bridge_port_list_impl,
    bridge_vlan_list_impl,
    dhcp_lease_list_impl,
    dhcp_network_list_impl,
    dhcp_server_list_impl,
    dns_get_impl,
    dns_resolve_impl,
    file_list_impl,
    firewall_address_list_list_impl,
    firewall_filter_list_impl,
    firewall_nat_list_impl,
    interface_get_impl,
    interface_list_impl,
    interface_monitor_impl,
    ip_address_get_impl,
    ip_address_list_impl,
    ip_route_get_impl,
    ip_route_list_impl,
    ppp_active_list_impl,
    ppp_secret_list_impl,
    resource_listen_impl,
    resource_print_impl,
    system_clock_get_impl,
    system_identity_get_impl,
    system_resource_get_impl,
    tool_ping_impl,
    tool_traceroute_impl,
    vlan_list_impl,
    wireguard_interface_list_impl,
    wireguard_peer_list_impl,
)
from mikrotik_mcp.server_helpers import safe_name_component


SENSITIVE_KEYS = {
    "password",
    "private-key",
    "preshared-key",
    "contents",
}


@dataclass(slots=True)
class Discovery:
    interface_name: str
    interface_item_id: str
    secondary_interface_name: str
    ip_address: str
    ip_item_id: str
    secondary_ip_address: str
    route_dst: str
    route_item_id: str
    secondary_route_dst: str
    route_gateway: str
    bridge_name: str
    bridge_port_interface: str
    ppp_secret_name: str
    firewall_list_name: str
    firewall_list_address: str
    wireguard_interface: str
    file_directory: str


@dataclass(slots=True)
class SmokeCase:
    command: str
    label: str
    runner: Callable[[Any, Discovery], Any]


def _first(items: list[dict[str, str]], *, field: str, fallback: str) -> str:
    for item in items:
        value = item.get(field, "").strip()
        if value:
            return value
    return fallback


def discover(client: Any) -> Discovery:
    interfaces = interface_list_impl(client, running_only=False, disabled=False)
    if not interfaces:
        raise RuntimeError("Live smoke discovery requires at least one enabled interface")

    interface_name = _first(interfaces, field="name", fallback="ether1")
    interface_record = interface_get_impl(client, name=interface_name)
    interface_item_id = interface_record.get(".id", "")
    secondary_interface_name = _first(interfaces[1:], field="name", fallback=interface_name)

    addresses = ip_address_list_impl(client, interface=None, disabled=False)
    if not addresses:
        raise RuntimeError("Live smoke discovery requires at least one IP address")
    ip_address = _first(addresses, field="address", fallback="192.168.88.1/24")
    ip_record = ip_address_get_impl(client, address=ip_address)
    ip_item_id = ip_record.get(".id", "")
    secondary_ip_address = _first(addresses[1:], field="address", fallback=ip_address)

    routes = ip_route_list_impl(client, dst_address=None, disabled=None)
    if not routes:
        raise RuntimeError("Live smoke discovery requires at least one route")
    route_dst = _first(routes, field="dst-address", fallback="0.0.0.0/0")
    route_record = ip_route_get_impl(client, dst_address=route_dst)
    route_item_id = route_record.get(".id", "")
    secondary_route_dst = _first(routes[1:], field="dst-address", fallback=route_dst)
    route_gateway = route_record.get("gateway", "").split("%", 1)[0].strip() or "1.1.1.1"

    bridges = bridge_list_impl(client, name=None, disabled=False)
    bridge_name = _first(bridges, field="name", fallback="bridge")

    bridge_ports = bridge_port_list_impl(client, bridge=bridge_name, interface=None, disabled=False)
    bridge_port_interface = _first(bridge_ports, field="interface", fallback=interface_name)

    ppp_secrets = ppp_secret_list_impl(client, name=None, service=None, disabled=False)
    ppp_secret_name = _first(ppp_secrets, field="name", fallback="vpn")

    firewall_entries = firewall_address_list_list_impl(client, list_name=None, address=None, disabled=False)
    firewall_list_name = _first(firewall_entries, field="list", fallback="wan-ip")
    firewall_list_address = _first(firewall_entries, field="address", fallback="127.0.0.1")

    wireguard_interfaces = wireguard_interface_list_impl(client, name=None, disabled=False)
    wireguard_interface = _first(wireguard_interfaces, field="name", fallback="back-to-home-vpn")

    files = file_list_impl(client, directory=None, name=None, file_type="directory")
    file_directory = _first(files, field="name", fallback="backups")

    if not interface_item_id:
        raise RuntimeError(f"Could not resolve item id for interface '{interface_name}'")
    if not ip_item_id:
        raise RuntimeError(f"Could not resolve item id for IP address '{ip_address}'")
    if not route_item_id:
        raise RuntimeError(f"Could not resolve item id for route '{route_dst}'")

    return Discovery(
        interface_name=interface_name,
        interface_item_id=interface_item_id,
        secondary_interface_name=secondary_interface_name,
        ip_address=ip_address,
        ip_item_id=ip_item_id,
        secondary_ip_address=secondary_ip_address,
        route_dst=route_dst,
        route_item_id=route_item_id,
        secondary_route_dst=secondary_route_dst,
        route_gateway=route_gateway,
        bridge_name=bridge_name,
        bridge_port_interface=bridge_port_interface,
        ppp_secret_name=ppp_secret_name,
        firewall_list_name=firewall_list_name,
        firewall_list_address=firewall_list_address,
        wireguard_interface=wireguard_interface,
        file_directory=file_directory,
    )


def build_cases() -> list[SmokeCase]:
    return [
        SmokeCase("resource_print", "interface by name", lambda c, d: resource_print_impl(c, menu="/interface", proplist=[".id", "name"], queries=[f"name={d.interface_name}"])),
        SmokeCase("resource_print", "bridge addresses", lambda c, d: resource_print_impl(c, menu="/ip/address", proplist=["address", "interface"], queries=[f"interface={d.bridge_name}"])),
        SmokeCase("resource_print", "ppp secret by name", lambda c, d: resource_print_impl(c, menu="/ppp/secret", proplist=["name", "service"], queries=[f"name={d.ppp_secret_name}"])),
        SmokeCase("resource_listen", "interface listen", lambda c, d: resource_listen_impl(c, menu="/interface", proplist=["name", "running"], queries=[f"name={d.interface_name}"], tag="smoke-listen-1", max_events=1)),
        SmokeCase("resource_listen", "ip address listen", lambda c, d: resource_listen_impl(c, menu="/ip/address", proplist=["address", "interface"], queries=[f"interface={d.bridge_name}"], tag="smoke-listen-2", max_events=1)),
        SmokeCase("resource_listen", "file listen", lambda c, _d: resource_listen_impl(c, menu="/file", proplist=["name", "type"], queries=["type=directory"], tag="smoke-listen-3", max_events=1)),
        SmokeCase("tool_ping", "default route gateway", lambda c, d: tool_ping_impl(c, address=d.route_gateway, count=1)),
        SmokeCase("tool_ping", "router lan ip", lambda c, d: tool_ping_impl(c, address=d.ip_address.split("/")[0], count=1, interface=d.bridge_name)),
        SmokeCase("tool_ping", "public dns", lambda c, _d: tool_ping_impl(c, address="1.1.1.1", count=1)),
        SmokeCase("tool_traceroute", "default route gateway", lambda c, d: tool_traceroute_impl(c, address=d.route_gateway, count=1, max_hops=3)),
        SmokeCase("tool_traceroute", "public dns", lambda c, _d: tool_traceroute_impl(c, address="1.1.1.1", count=1, max_hops=5)),
        SmokeCase("tool_traceroute", "router lan ip", lambda c, d: tool_traceroute_impl(c, address=d.ip_address.split("/")[0], count=1, max_hops=2, interface=d.bridge_name)),
        SmokeCase("dns_resolve", "example.com", lambda c, _d: dns_resolve_impl(c, name="example.com")),
        SmokeCase("dns_resolve", "cloudflare via 1.1.1.1", lambda c, _d: dns_resolve_impl(c, name="cloudflare.com", server="1.1.1.1")),
        SmokeCase("dns_resolve", "routeros via 9.9.9.9", lambda c, _d: dns_resolve_impl(c, name="routeros.com", server="9.9.9.9")),
        SmokeCase("interface_monitor", "primary interface", lambda c, d: interface_monitor_impl(c, name=d.interface_name)),
        SmokeCase("interface_monitor", "bridge", lambda c, d: interface_monitor_impl(c, name=d.bridge_name)),
        SmokeCase("interface_monitor", "wireguard", lambda c, d: interface_monitor_impl(c, name=d.wireguard_interface)),
        SmokeCase("system_resource_get", "baseline", lambda c, _d: system_resource_get_impl(c)),
        SmokeCase("system_resource_get", "repeat 1", lambda c, _d: system_resource_get_impl(c)),
        SmokeCase("system_resource_get", "repeat 2", lambda c, _d: system_resource_get_impl(c)),
        SmokeCase("system_identity_get", "baseline", lambda c, _d: system_identity_get_impl(c)),
        SmokeCase("system_identity_get", "repeat 1", lambda c, _d: system_identity_get_impl(c)),
        SmokeCase("system_identity_get", "repeat 2", lambda c, _d: system_identity_get_impl(c)),
        SmokeCase("system_clock_get", "baseline", lambda c, _d: system_clock_get_impl(c)),
        SmokeCase("system_clock_get", "repeat 1", lambda c, _d: system_clock_get_impl(c)),
        SmokeCase("system_clock_get", "repeat 2", lambda c, _d: system_clock_get_impl(c)),
        SmokeCase("interface_list", "running only", lambda c, _d: interface_list_impl(c, running_only=True, disabled=False)),
        SmokeCase("interface_list", "disabled only", lambda c, _d: interface_list_impl(c, running_only=False, disabled=True)),
        SmokeCase("interface_list", "enabled only", lambda c, _d: interface_list_impl(c, running_only=False, disabled=False)),
        SmokeCase("interface_get", "by name", lambda c, d: interface_get_impl(c, name=d.interface_name)),
        SmokeCase("interface_get", "by item id", lambda c, d: interface_get_impl(c, item_id=d.interface_item_id)),
        SmokeCase("interface_get", "secondary name", lambda c, d: interface_get_impl(c, name=d.secondary_interface_name)),
        SmokeCase("ip_address_list", "bridge", lambda c, d: ip_address_list_impl(c, interface=d.bridge_name, disabled=False)),
        SmokeCase("ip_address_list", "wireguard", lambda c, d: ip_address_list_impl(c, interface=d.wireguard_interface, disabled=False)),
        SmokeCase("ip_address_list", "missing interface", lambda c, _d: ip_address_list_impl(c, interface="definitely-missing", disabled=False)),
        SmokeCase("ip_address_get", "by address", lambda c, d: ip_address_get_impl(c, address=d.ip_address)),
        SmokeCase("ip_address_get", "by item id", lambda c, d: ip_address_get_impl(c, item_id=d.ip_item_id)),
        SmokeCase("ip_address_get", "secondary address", lambda c, d: ip_address_get_impl(c, address=d.secondary_ip_address)),
        SmokeCase("ip_route_list", "default route", lambda c, d: ip_route_list_impl(c, dst_address=d.route_dst, disabled=None)),
        SmokeCase("ip_route_list", "secondary route", lambda c, d: ip_route_list_impl(c, dst_address=d.secondary_route_dst, disabled=None)),
        SmokeCase("ip_route_list", "missing route", lambda c, _d: ip_route_list_impl(c, dst_address="203.0.113.0/24", disabled=None)),
        SmokeCase("ip_route_get", "by destination", lambda c, d: ip_route_get_impl(c, dst_address=d.route_dst)),
        SmokeCase("ip_route_get", "by item id", lambda c, d: ip_route_get_impl(c, item_id=d.route_item_id)),
        SmokeCase("ip_route_get", "secondary destination", lambda c, d: ip_route_get_impl(c, dst_address=d.secondary_route_dst)),
        SmokeCase("dhcp_lease_list", "active only", lambda c, _d: dhcp_lease_list_impl(c, active_only=True)),
        SmokeCase("dhcp_lease_list", "missing address", lambda c, _d: dhcp_lease_list_impl(c, address="192.168.16.200", active_only=False)),
        SmokeCase("dhcp_lease_list", "missing mac", lambda c, _d: dhcp_lease_list_impl(c, mac_address="00:00:00:00:00:00", active_only=False)),
        SmokeCase("dhcp_server_list", "baseline", lambda c, _d: dhcp_server_list_impl(c)),
        SmokeCase("dhcp_server_list", "repeat 1", lambda c, _d: dhcp_server_list_impl(c)),
        SmokeCase("dhcp_server_list", "repeat 2", lambda c, _d: dhcp_server_list_impl(c)),
        SmokeCase("dhcp_network_list", "baseline", lambda c, _d: dhcp_network_list_impl(c)),
        SmokeCase("dhcp_network_list", "repeat 1", lambda c, _d: dhcp_network_list_impl(c)),
        SmokeCase("dhcp_network_list", "repeat 2", lambda c, _d: dhcp_network_list_impl(c)),
        SmokeCase("dns_get", "baseline", lambda c, _d: dns_get_impl(c)),
        SmokeCase("dns_get", "repeat 1", lambda c, _d: dns_get_impl(c)),
        SmokeCase("dns_get", "repeat 2", lambda c, _d: dns_get_impl(c)),
        SmokeCase("bridge_list", "by name", lambda c, d: bridge_list_impl(c, name=d.bridge_name, disabled=False)),
        SmokeCase("bridge_list", "missing bridge", lambda c, _d: bridge_list_impl(c, name="missing-bridge", disabled=False)),
        SmokeCase("bridge_list", "all enabled", lambda c, _d: bridge_list_impl(c, name=None, disabled=False)),
        SmokeCase("bridge_port_list", "bridge and interface", lambda c, d: bridge_port_list_impl(c, bridge=d.bridge_name, interface=d.bridge_port_interface, disabled=False)),
        SmokeCase("bridge_port_list", "bridge only", lambda c, d: bridge_port_list_impl(c, bridge=d.bridge_name, interface=None, disabled=False)),
        SmokeCase("bridge_port_list", "missing interface", lambda c, d: bridge_port_list_impl(c, bridge=d.bridge_name, interface="missing-port", disabled=False)),
        SmokeCase("bridge_vlan_list", "bridge", lambda c, d: bridge_vlan_list_impl(c, bridge=d.bridge_name, vlan_ids=None, disabled=False)),
        SmokeCase("bridge_vlan_list", "vlan 1", lambda c, d: bridge_vlan_list_impl(c, bridge=d.bridge_name, vlan_ids="1", disabled=False)),
        SmokeCase("bridge_vlan_list", "vlan 4094", lambda c, d: bridge_vlan_list_impl(c, bridge=d.bridge_name, vlan_ids="4094", disabled=False)),
        SmokeCase("vlan_list", "all enabled", lambda c, _d: vlan_list_impl(c, name=None, interface=None, disabled=False)),
        SmokeCase("vlan_list", "by name", lambda c, _d: vlan_list_impl(c, name="vlan10", interface=None, disabled=None)),
        SmokeCase("vlan_list", "by parent bridge", lambda c, d: vlan_list_impl(c, name=None, interface=d.bridge_name, disabled=False)),
        SmokeCase("firewall_filter_list", "input accept", lambda c, _d: firewall_filter_list_impl(c, chain="input", action="accept", disabled=False)),
        SmokeCase("firewall_filter_list", "forward drop", lambda c, _d: firewall_filter_list_impl(c, chain="forward", action="drop", disabled=False)),
        SmokeCase("firewall_filter_list", "output any", lambda c, _d: firewall_filter_list_impl(c, chain="output", action=None, disabled=False)),
        SmokeCase("firewall_nat_list", "srcnat masquerade", lambda c, _d: firewall_nat_list_impl(c, chain="srcnat", action="masquerade", disabled=False)),
        SmokeCase("firewall_nat_list", "dstnat", lambda c, _d: firewall_nat_list_impl(c, chain="dstnat", action="dst-nat", disabled=False)),
        SmokeCase("firewall_nat_list", "disabled srcnat", lambda c, _d: firewall_nat_list_impl(c, chain="srcnat", action="masquerade", disabled=True)),
        SmokeCase("firewall_address_list_list", "discovered list", lambda c, d: firewall_address_list_list_impl(c, list_name=d.firewall_list_name, address=None, disabled=False)),
        SmokeCase("firewall_address_list_list", "discovered entry", lambda c, d: firewall_address_list_list_impl(c, list_name=d.firewall_list_name, address=d.firewall_list_address, disabled=False)),
        SmokeCase("firewall_address_list_list", "missing list", lambda c, _d: firewall_address_list_list_impl(c, list_name="definitely-missing-list", address=None, disabled=False)),
        SmokeCase("ppp_active_list", "all", lambda c, _d: ppp_active_list_impl(c, service=None, name=None)),
        SmokeCase("ppp_active_list", "pppoe only", lambda c, _d: ppp_active_list_impl(c, service="pppoe", name=None)),
        SmokeCase("ppp_active_list", "by name", lambda c, d: ppp_active_list_impl(c, service=None, name=d.ppp_secret_name)),
        SmokeCase("ppp_secret_list", "by name", lambda c, d: ppp_secret_list_impl(c, name=d.ppp_secret_name, service=None, disabled=False)),
        SmokeCase("ppp_secret_list", "service any", lambda c, _d: ppp_secret_list_impl(c, name=None, service="any", disabled=False)),
        SmokeCase("ppp_secret_list", "missing secret", lambda c, _d: ppp_secret_list_impl(c, name="definitely-missing-secret", service=None, disabled=False)),
        SmokeCase("wireguard_interface_list", "by name", lambda c, d: wireguard_interface_list_impl(c, name=d.wireguard_interface, disabled=False)),
        SmokeCase("wireguard_interface_list", "all enabled", lambda c, _d: wireguard_interface_list_impl(c, name=None, disabled=False)),
        SmokeCase("wireguard_interface_list", "missing interface", lambda c, _d: wireguard_interface_list_impl(c, name="definitely-missing-wg", disabled=False)),
        SmokeCase("wireguard_peer_list", "all peers", lambda c, d: wireguard_peer_list_impl(c, interface=d.wireguard_interface, disabled=False)),
        SmokeCase("wireguard_peer_list", "disabled peers", lambda c, d: wireguard_peer_list_impl(c, interface=d.wireguard_interface, disabled=True)),
        SmokeCase("wireguard_peer_list", "missing interface", lambda c, _d: wireguard_peer_list_impl(c, interface="definitely-missing-wg", disabled=False)),
        SmokeCase("file_list", "directory by name", lambda c, d: file_list_impl(c, directory=None, name=d.file_directory, file_type="directory")),
        SmokeCase("file_list", "backup scripts", lambda c, _d: file_list_impl(c, directory="backups", name=None, file_type="script")),
        SmokeCase("file_list", "missing directory", lambda c, _d: file_list_impl(c, directory="definitely-missing-dir", name=None, file_type="script")),
    ]


def summarize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, list):
        keys = []
        if result:
            keys = sorted(key for key in result[0] if key not in SENSITIVE_KEYS)
        return {"kind": "list", "count": len(result), "sample_keys": keys}
    if isinstance(result, dict):
        keys = sorted(key for key in result if key not in SENSITIVE_KEYS)
        summary: dict[str, Any] = {"kind": "dict", "keys": keys}
        for key in ("tag", "empty", "cancelled", "limit_reached"):
            if key in result:
                summary[key] = result[key]
        if "events" in result and isinstance(result["events"], list):
            summary["event_count"] = len(result["events"])
        return summary
    return {"kind": type(result).__name__}


def run_smoke(host: str, *, timeout: float) -> dict[str, Any]:
    client = load_settings(host)
    client.timeout = timeout
    started_at = datetime.now(UTC)
    client.open()
    try:
        discovery = discover(client)
        cases = build_cases()
        results: list[dict[str, Any]] = []
        for case in cases:
            began = time.perf_counter()
            try:
                result = case.runner(client, discovery)
                results.append(
                    {
                        "command": case.command,
                        "label": case.label,
                        "status": "passed",
                        "duration_ms": round((time.perf_counter() - began) * 1000, 2),
                        "summary": summarize_result(result),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "command": case.command,
                        "label": case.label,
                        "status": "failed",
                        "duration_ms": round((time.perf_counter() - began) * 1000, 2),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    finally:
        client.close()

    commands = sorted({item["command"] for item in results})
    by_command: list[dict[str, Any]] = []
    for command in commands:
        command_results = [item for item in results if item["command"] == command]
        passed = sum(item["status"] == "passed" for item in command_results)
        failed = len(command_results) - passed
        by_command.append(
            {
                "command": command,
                "passed": passed,
                "failed": failed,
                "status": "passed" if failed == 0 else "failed",
            }
        )

    return {
        "host": host,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "timeout_seconds": timeout,
        "summary": {
            "commands_total": len(by_command),
            "commands_passed": sum(item["status"] == "passed" for item in by_command),
            "commands_failed": sum(item["status"] == "failed" for item in by_command),
            "cases_total": len(results),
            "cases_passed": sum(item["status"] == "passed" for item in results),
            "cases_failed": sum(item["status"] == "failed" for item in results),
        },
        "commands": by_command,
        "cases": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Live Smoke Report",
        "",
        f"- Host: `{report['host']}`",
        f"- Started: `{report['started_at']}`",
        f"- Completed: `{report['completed_at']}`",
        f"- Timeout per socket read: `{report['timeout_seconds']}s`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Commands total | {report['summary']['commands_total']} |",
        f"| Commands passed | {report['summary']['commands_passed']} |",
        f"| Commands failed | {report['summary']['commands_failed']} |",
        f"| Cases total | {report['summary']['cases_total']} |",
        f"| Cases passed | {report['summary']['cases_passed']} |",
        f"| Cases failed | {report['summary']['cases_failed']} |",
        "",
        "## Command Status",
        "",
        "| Command | Passed | Failed | Status |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["commands"]:
        lines.append(f"| `{item['command']}` | {item['passed']} | {item['failed']} | {item['status']} |")

    lines.extend(["", "## Failed Cases", ""])
    failed_cases = [item for item in report["cases"] if item["status"] == "failed"]
    if not failed_cases:
        lines.append("None.")
    else:
        lines.extend([
            "| Command | Case | Error |",
            "| --- | --- | --- |",
        ])
        for item in failed_cases:
            error = str(item.get("error", "")).replace("|", "\\|")
            lines.append(f"| `{item['command']}` | {item['label']} | `{error}` |")

    lines.extend(["", "## Case Details", ""])
    lines.extend([
        "| Command | Case | Status | Duration ms | Summary |",
        "| --- | --- | --- | --- | --- |",
    ])
    for item in report["cases"]:
        summary = item.get("summary") or {"error": item.get("error", "")}
        summary_text = json.dumps(summary, sort_keys=True).replace("|", "\\|")
        lines.append(
            f"| `{item['command']}` | {item['label']} | {item['status']} | {item['duration_ms']} | `{summary_text}` |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live smoke checks for read-only MikroTik MCP commands")
    parser.add_argument("host", help="Router host or IP address")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "reports" / "live-smoke"),
        help="Directory for JSON and Markdown reports",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Socket read timeout in seconds for each RouterOS client connection",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_smoke(args.host, timeout=args.timeout)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    host_slug = safe_name_component(args.host, default="router")
    stem = f"{timestamp}-{host_slug}-read-only"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"Wrote JSON report: {json_path}")
    print(f"Wrote Markdown report: {md_path}")
    print(
        "Summary: "
        f"{report['summary']['commands_passed']}/{report['summary']['commands_total']} commands passed, "
        f"{report['summary']['cases_failed']} failed cases"
    )
    return 0 if report["summary"]["commands_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
