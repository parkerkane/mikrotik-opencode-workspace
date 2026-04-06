from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from mikrotik_mcp.app import create_app
from mikrotik_mcp import runtime
from mikrotik_mcp.client import ListenResult, RouterOSError
from mikrotik_mcp.downloads import RouterFileDownloadError
from mikrotik_mcp import server_helpers
from mikrotik_mcp.tool_impls import files as file_tool_impls
from mikrotik_mcp.tool_impls import core
from mikrotik_mcp.server import (
    bridge_add_impl,
    bridge_list_impl,
    bridge_port_add_impl,
    bridge_port_list_impl,
    bridge_port_remove_impl,
    bridge_remove_impl,
    bridge_vlan_add_impl,
    bridge_vlan_list_impl,
    bridge_vlan_remove_impl,
    command_cancel_impl,
    command_run_impl,
    dhcp_lease_list_impl,
    dhcp_network_list_impl,
    dhcp_server_list_impl,
    dns_get_impl,
    dns_resolve_impl,
    dns_set_impl,
    healthcheck_impl,
    firewall_address_list_add_impl,
    firewall_address_list_list_impl,
    firewall_address_list_remove_impl,
    firewall_filter_add_impl,
    firewall_filter_list_impl,
    firewall_filter_remove_impl,
    firewall_filter_set_impl,
    firewall_nat_add_impl,
    firewall_nat_list_impl,
    firewall_nat_remove_impl,
    firewall_nat_set_impl,
    firewall_rule_move_impl,
    file_download_impl,
    file_list_impl,
    interface_get_impl,
    interface_list_impl,
    interface_monitor_impl,
    ip_address_get_impl,
    ip_address_list_impl,
    ip_route_get_impl,
    ip_route_list_impl,
    ppp_active_list_impl,
    ppp_secret_add_impl,
    ppp_secret_list_impl,
    ppp_secret_remove_impl,
    resource_add_impl,
    resource_listen_impl,
    resource_print_impl,
    resource_remove_impl,
    resource_set_impl,
    system_backup_collect_impl,
    system_backup_save_impl,
    system_clock_get_impl,
    system_export_impl,
    system_identity_get_impl,
    system_resource_get_impl,
    tool_ping_impl,
    tool_traceroute_impl,
    vlan_add_impl,
    vlan_list_impl,
    vlan_remove_impl,
    wireguard_interface_add_impl,
    wireguard_interface_list_impl,
    wireguard_peer_add_impl,
    wireguard_peer_list_impl,
    wireguard_peer_remove_impl,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]


class RecordingDownloader:
    def __init__(self, *, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.calls: list[tuple[str, Path]] = []

    def download_file(self, router_path: str, local_path: str | Path) -> None:
        path = Path(local_path)
        self.calls.append((router_path, path))
        if self.fail_on_call == len(self.calls):
            raise RouterFileDownloadError("download failed")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"artifact")


def isolated_client_mock(inner_client: Mock) -> MagicMock:
    isolated = MagicMock()
    isolated.__enter__.return_value = inner_client
    isolated.__exit__.return_value = None
    return isolated


def test_runtime_main_starts_server_without_eager_api_login(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock()
    app = Mock()

    monkeypatch.setattr(runtime, "load_settings", lambda host: client)
    monkeypatch.setattr(runtime, "create_app", lambda loaded_client: app)

    runtime.main(["router.local"])

    client.open.assert_not_called()
    app.run.assert_called_once_with(transport="stdio")
    client.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_app_system_resource_get_returns_markdown_and_structured_content(socket_enabled) -> None:
    client = Mock()
    client.print.return_value = [{"version": "7.17", "uptime": "1d2h", "board-name": "RB5009"}]

    result = await create_app(client).call_tool("system_resource_get", {})

    assert result.structuredContent == {"version": "7.17", "uptime": "1d2h", "board-name": "RB5009"}
    assert len(result.content) == 1
    assert "System resource: RouterOS 7.17, uptime 1d2h" in result.content[0].text
    assert "| Field | Value |" in result.content[0].text
    assert "| board-name | RB5009 |" in result.content[0].text


@pytest.mark.asyncio
async def test_app_interface_list_returns_markdown_table_and_wrapped_structured_content(socket_enabled) -> None:
    client = Mock()
    client.print.return_value = [
        {
            "name": "ether1",
            "type": "ether",
            "running": "true",
            "disabled": "false",
            "actual-mtu": "1500",
            "mac-address": "00:11:22:33:44:55",
        }
    ]

    result = await create_app(client).call_tool("interface_list", {})

    assert result.structuredContent == {"result": client.print.return_value}
    assert "Interfaces: 1 interface" in result.content[0].text
    assert "| Name | Type | Running | Disabled | MTU | MAC Address |" in result.content[0].text
    assert "| ether1 | ether | yes | no | 1500 | 00:11:22:33:44:55 |" in result.content[0].text


@pytest.mark.asyncio
async def test_app_dhcp_network_list_formats_empty_values_consistently(socket_enabled) -> None:
    client = Mock()
    client.print.return_value = [{"address": "192.0.2.0/24", "gateway": "192.0.2.1", "dns-server": "", "domain": "", "ntp-server": ""}]

    result = await create_app(client).call_tool("dhcp_network_list", {})

    assert result.structuredContent == {"result": client.print.return_value}
    assert "DHCP Networks: 1 DHCP network" in result.content[0].text
    assert "| 192.0.2.0/24 | 192.0.2.1 | - | - | - |" in result.content[0].text


@pytest.mark.asyncio
async def test_app_dns_get_returns_summary_line_and_structured_content(socket_enabled) -> None:
    client = Mock()
    client.print.return_value = [{"servers": "1.1.1.1,8.8.8.8", "allow-remote-requests": "true", "cache-size": "2048KiB"}]

    result = await create_app(client).call_tool("dns_get", {})

    assert result.structuredContent == client.print.return_value[0]
    assert "DNS settings: servers 1.1.1.1,8.8.8.8, remote requests yes" in result.content[0].text
    assert "| servers | 1.1.1.1,8.8.8.8 |" in result.content[0].text


@pytest.mark.asyncio
async def test_app_healthcheck_returns_api_and_scp_statuses(socket_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock(host="router.test")
    client.port = 8729
    client.use_ssl = True
    client.username = "api-user"
    client.password = "api-pass"
    client.print.return_value = [{"name": "lab-router"}]
    client.tls_session_info = lambda: {
        "subject": "commonName=Router",
        "issuer": "commonName=Router CA",
        "serial_number": "ABCD1234",
        "not_before": "Apr  6 15:39:31 2026 GMT",
        "not_after": "Apr  3 15:39:31 2036 GMT",
        "subject_alt_names": ["router.test"],
        "sha256_fingerprint": "FINGERPRINT",
        "tls_version": "TLSv1.2",
        "cipher": "ECDHE-RSA-AES256-GCM-SHA384",
        "cipher_bits": 256,
        "hostname_verified": True,
    }
    monkeypatch.setenv("MIKROTIK_USER", "api-user")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "api-pass")
    monkeypatch.setenv("MIKROTIK_SCP_USER", "scp-user")
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "scp-pass")
    monkeypatch.setenv("MIKROTIK_SCP_HOST", "files.router.test")

    class Settings:
        host = "files.router.test"
        port = 21

    downloader = Mock()
    downloader.check_connection.return_value = {
        "working_directory": "/",
        "listing_count": 2,
        "listing_sample": ["backups", "flash"],
        "operation": "normalize+listdir_attr",
    }
    monkeypatch.setattr(core, "load_file_transfer_settings", lambda host: Settings())
    monkeypatch.setattr(core, "SCPFileDownloader", lambda settings: downloader)

    result = await create_app(client).call_tool("healthcheck", {})

    assert result.structuredContent["success"] is True
    assert result.structuredContent["status"] == "healthy"
    assert result.structuredContent["target_host"] == "router.test"
    assert result.structuredContent["timestamp"].endswith("Z")
    assert result.structuredContent["config"] == {
        "api_credentials_configured": True,
        "api_host": "router.test",
        "api_port": 8729,
        "api_tls": True,
        "scp_credentials_configured": True,
        "scp_host_override": True,
        "scp_port_override": False,
        "resolved_host": "files.router.test",
    }
    assert result.structuredContent["api"] == {
        "ok": True,
        "status": "ok",
        "code": "api.ok",
        "message": "RouterOS API returned system identity",
        "identity": {"name": "lab-router"},
        "host": "router.test",
        "port": 8729,
        "tls": True,
        "certificate": {
            "subject": "commonName=Router",
            "issuer": "commonName=Router CA",
            "serial_number": "ABCD1234",
            "not_before": "Apr  6 15:39:31 2026 GMT",
            "not_after": "Apr  3 15:39:31 2036 GMT",
            "subject_alt_names": ["router.test"],
            "sha256_fingerprint": "FINGERPRINT",
            "tls_version": "TLSv1.2",
            "cipher": "ECDHE-RSA-AES256-GCM-SHA384",
            "cipher_bits": 256,
            "hostname_verified": True,
        },
        "duration_ms": result.structuredContent["api"]["duration_ms"],
    }
    assert result.structuredContent["scp"] == {
        "ok": True,
        "status": "ok",
        "code": "scp.ok",
        "message": "SCP login and directory probe succeeded for files.router.test:21",
        "host": "files.router.test",
        "port": 21,
        "probe": {
            "working_directory": "/",
            "listing_count": 2,
            "listing_sample": ["backups", "flash"],
            "operation": "normalize+listdir_attr",
        },
        "duration_ms": result.structuredContent["scp"]["duration_ms"],
    }
    assert isinstance(result.structuredContent["api"]["duration_ms"], int)
    assert isinstance(result.structuredContent["scp"]["duration_ms"], int)
    assert "Healthcheck: healthy" in result.content[0].text
    assert "| status | healthy |" in result.content[0].text
    assert "| target-host | router.test |" in result.content[0].text
    assert "| api-status | ok |" in result.content[0].text
    assert "| api-code | api.ok |" in result.content[0].text
    assert "| api-name | lab-router |" in result.content[0].text
    assert "| api-tls-version | TLSv1.2 |" in result.content[0].text
    assert "| api-cert-subject | commonName=Router |" in result.content[0].text
    assert "| api-cert-not-after | Apr  3 15:39:31 2036 GMT |" in result.content[0].text
    assert "| scp-status | ok |" in result.content[0].text
    assert "| scp-probe | normalize+listdir_attr |" in result.content[0].text
    downloader.check_connection.assert_called_once_with()


@pytest.mark.asyncio
async def test_app_tool_ping_returns_formatted_markdown_and_structured_content(socket_enabled) -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = [
        {"seq": "0", "host": "192.0.2.1", "size": "56", "ttl": "64", "time": "4ms", "status": "reachable"}
    ]
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = await create_app(client).call_tool("tool_ping", {"address": "192.0.2.1", "count": 1})

    assert result.structuredContent == {"address": "192.0.2.1", "result": isolated_client.run.return_value}
    assert "Ping 192.0.2.1: 1 probe" in result.content[0].text
    assert "| Seq | Host | Size | TTL | Time | Status |" in result.content[0].text
    assert "| 0 | 192.0.2.1 | 56 | 64 | 4ms | reachable |" in result.content[0].text


@pytest.mark.asyncio
async def test_app_tool_traceroute_returns_formatted_markdown_and_structured_content(socket_enabled) -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = [
        {
            "hop": "1",
            "host": "edge-router",
            "address": "198.51.100.1",
            "loss": "0%",
            "last": "2ms",
            "avg": "2ms",
            "best": "2ms",
            "worst": "3ms",
            "status": "reachable",
        }
    ]
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = await create_app(client).call_tool("tool_traceroute", {"address": "example.com"})

    assert result.structuredContent == {"address": "example.com", "result": isolated_client.run.return_value}
    assert "Traceroute example.com: 1 hop" in result.content[0].text
    assert "| Hop | Host | Address | Loss | Last | Avg | Best | Worst | Status |" in result.content[0].text
    assert "| 1 | edge-router | 198.51.100.1 | 0% | 2ms | 2ms | 2ms | 3ms | reachable |" in result.content[0].text


@pytest.mark.asyncio
async def test_app_dns_resolve_returns_summary_line_and_structured_content(socket_enabled) -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = {"ret": "93.184.216.34"}
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = await create_app(client).call_tool("dns_resolve", {"name": "example.com"})

    assert result.structuredContent == {"name": "example.com", "address": "93.184.216.34"}
    assert "DNS resolve: example.com -> 93.184.216.34" in result.content[0].text
    assert "| name | example.com |" in result.content[0].text
    assert "| address | 93.184.216.34 |" in result.content[0].text


@pytest.mark.asyncio
async def test_app_interface_monitor_returns_summary_line_and_structured_content(socket_enabled) -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = [
        {
            "status": "running",
            "rx-bits-per-second": "1000000",
            "tx-bits-per-second": "250000",
            "rx-packets-per-second": "125",
            "tx-packets-per-second": "40",
        }
    ]
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = await create_app(client).call_tool("interface_monitor", {"name": "ether1"})

    assert result.structuredContent == {
        "name": "ether1",
        "status": "running",
        "rx-bits-per-second": "1000000",
        "tx-bits-per-second": "250000",
        "rx-packets-per-second": "125",
        "tx-packets-per-second": "40",
    }
    assert "Interface monitor ether1: rx 1000000, tx 250000" in result.content[0].text
    assert "| status | running |" in result.content[0].text
    assert "| rx-bits-per-second | 1000000 |" in result.content[0].text


@pytest.mark.asyncio
async def test_app_resource_print_remains_raw_json_output(socket_enabled) -> None:
    client = Mock()
    client.print.return_value = [{"name": "ether1", "running": "true"}]

    result = await create_app(client).call_tool("resource_print", {"menu": "/interface"})

    assert result[0].text == '{\n  "name": "ether1",\n  "running": "true"\n}'


def test_resource_print_calls_client_and_returns_normalized_items() -> None:
    client = Mock()
    client.print.return_value = [
        {"name": "ether1", "running": "true"},
        {"name": "ether2", "running": "false"},
    ]

    result = resource_print_impl(
        client,
        menu="/interface",
        proplist=["name", "running"],
        queries=["running=true"],
        attributes={"detail": True},
    )

    assert result == [
        {"name": "ether1", "running": "true"},
        {"name": "ether2", "running": "false"},
    ]
    client.print.assert_called_once_with(
        "/interface",
        proplist=["name", "running"],
        queries=["running=true"],
        attrs={"detail": True},
    )


def test_resource_print_applies_jq_filter_after_normalization() -> None:
    client = Mock()
    client.print.return_value = [
        {"name": "ether1", "running": "true"},
        {"name": "ether2", "running": "false"},
    ]

    result = resource_print_impl(client, menu="/interface", jq_filter="map(select(.running == \"true\"))")

    assert result == [{"name": "ether1", "running": "true"}]


def test_resource_print_invalid_jq_filter_returns_clear_error() -> None:
    client = Mock()
    client.print.return_value = [{"name": "ether1"}]

    with pytest.raises(ValueError, match="Invalid jq_filter"):
        resource_print_impl(client, menu="/interface", jq_filter="[")


def test_resource_add_calls_client_and_returns_done_payload() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*4"}

    result = resource_add_impl(client, menu="/ip/address", attributes={"address": "192.0.2.10/24"})

    assert result == {"ret": "*4"}
    client.add.assert_called_once_with("/ip/address", attrs={"address": "192.0.2.10/24"})


def test_resource_set_calls_client_with_explicit_item_id() -> None:
    client = Mock()
    client.set.return_value = {"success": True}

    result = resource_set_impl(client, menu="/ip/address", item_id="*4", attributes={"disabled": True})

    assert result == {"success": True}
    client.set.assert_called_once_with("/ip/address", "*4", attrs={"disabled": True})


def test_resource_remove_calls_client_with_explicit_item_id() -> None:
    client = Mock()
    client.remove.return_value = {"success": True, "empty": True}

    result = resource_remove_impl(client, menu="/ip/address", item_id="*4")

    assert result == {"success": True, "empty": True}
    client.remove.assert_called_once_with("/ip/address", "*4")


def test_command_run_calls_client_and_returns_normalized_output() -> None:
    client = Mock()
    client.run.return_value = [{"host": "192.0.2.1", "status": "reachable"}]

    result = command_run_impl(
        client,
        command="/tool/ping",
        attributes={"address": "192.0.2.1", "count": 1},
        queries=["status=reachable"],
    )

    assert result == [{"host": "192.0.2.1", "status": "reachable"}]
    client.run.assert_called_once_with(
        "/tool/ping",
        attrs={"address": "192.0.2.1", "count": 1},
        queries=["status=reachable"],
    )


def test_resource_listen_calls_client_and_returns_bounded_payload() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.listen.return_value = ListenResult(
        tag="listen-1",
        records=[{"name": "ether1"}],
        done={"ret": "ok"},
        cancelled=True,
        limit_reached=True,
        cancel_done={"ret": "interrupted"},
    )
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = resource_listen_impl(
        client,
        menu="/interface",
        proplist=["name"],
        queries=["running=true"],
        attributes={"once": False},
        tag="listen-1",
        max_events=1,
    )

    assert result == {
        "tag": "listen-1",
        "events": [{"name": "ether1"}],
        "done": {"ret": "ok"},
        "traps": [],
        "empty": False,
        "cancelled": True,
        "limit_reached": True,
        "cancel_done": {"ret": "interrupted"},
    }
    isolated_client.listen.assert_called_once_with(
        "/interface",
        proplist=["name"],
        queries=["running=true"],
        attrs={"once": False},
        tag="listen-1",
        max_events=1,
    )
    client.isolated.assert_called_once_with()


def test_command_cancel_calls_client_and_returns_requested_tag() -> None:
    client = Mock()
    client.cancel.return_value = {"success": True}

    result = command_cancel_impl(client, tag="listen-1")

    assert result == {"tag": "listen-1", "success": True}
    client.cancel.assert_called_once_with("listen-1")


def test_tool_ping_runs_on_isolated_client_and_returns_records() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = [{"host": "192.0.2.1", "status": "reachable"}]
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = tool_ping_impl(
        client,
        address="192.0.2.1",
        count=3,
        interval="500ms",
        interface="ether1",
        packet_size=64,
    )

    assert result == [{"host": "192.0.2.1", "status": "reachable"}]
    isolated_client.run.assert_called_once_with(
        "/tool/ping",
        attrs={
            "address": "192.0.2.1",
            "count": 3,
            "interval": "500ms",
            "interface": "ether1",
            "size": 64,
        },
    )
    client.isolated.assert_called_once_with()


def test_tool_ping_returns_empty_list_when_router_only_returns_done() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = {"ret": "ok"}
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = tool_ping_impl(client, address="192.0.2.1")

    assert result == []


def test_tool_ping_propagates_router_errors() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.side_effect = RouterOSError("RouterOS command failed: timeout")
    client.isolated.return_value = isolated_client_mock(isolated_client)

    with pytest.raises(RouterOSError, match="timeout"):
        tool_ping_impl(client, address="192.0.2.1")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"address": "   "}, "address is required"),
        ({"address": "192.0.2.1", "count": 0}, "count must be at least 1"),
        ({"address": "192.0.2.1", "packet_size": 0}, "packet_size must be at least 1"),
        ({"address": "192.0.2.1", "interval": "   "}, "interval is required"),
    ],
)
def test_tool_ping_validates_inputs(kwargs: dict[str, object], message: str) -> None:
    client = Mock()

    with pytest.raises(ValueError, match=message):
        tool_ping_impl(client, **kwargs)


def test_tool_traceroute_runs_on_isolated_client_and_returns_records() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = [{"hop": "1", "host": "198.51.100.1", "status": "reachable"}]
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = tool_traceroute_impl(
        client,
        address="example.com",
        count=2,
        max_hops=20,
        interval="1s",
        interface="ether1",
        packet_size=64,
    )

    assert result == [{"hop": "1", "host": "198.51.100.1", "status": "reachable"}]
    isolated_client.run.assert_called_once_with(
        "/tool/traceroute",
        attrs={
            "address": "example.com",
            "count": 2,
            "max-hops": 20,
            "interval": "1s",
            "interface": "ether1",
            "size": 64,
        },
    )
    client.isolated.assert_called_once_with()


def test_tool_traceroute_returns_empty_list_when_router_only_returns_done() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = {"ret": "ok"}
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = tool_traceroute_impl(client, address="example.com")

    assert result == []


def test_tool_traceroute_propagates_router_errors() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.side_effect = RouterOSError("RouterOS command failed: no route to host")
    client.isolated.return_value = isolated_client_mock(isolated_client)

    with pytest.raises(RouterOSError, match="no route to host"):
        tool_traceroute_impl(client, address="example.com")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"address": "   "}, "address is required"),
        ({"address": "example.com", "count": 0}, "count must be at least 1"),
        ({"address": "example.com", "max_hops": 0}, "max_hops must be at least 1"),
        ({"address": "example.com", "packet_size": 0}, "packet_size must be at least 1"),
        ({"address": "example.com", "interval": "   "}, "interval is required"),
    ],
)
def test_tool_traceroute_validates_inputs(kwargs: dict[str, object], message: str) -> None:
    client = Mock()

    with pytest.raises(ValueError, match=message):
        tool_traceroute_impl(client, **kwargs)


def test_dns_resolve_returns_normalized_result() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = {"ret": "93.184.216.34"}
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = dns_resolve_impl(client, name="example.com", server="1.1.1.1")

    assert result == {"name": "example.com", "address": "93.184.216.34", "server": "1.1.1.1"}
    isolated_client.run.assert_called_once_with("/resolve", attrs={"domain-name": "example.com", "server": "1.1.1.1"})
    client.isolated.assert_called_once_with()


def test_dns_resolve_requires_name_and_server_when_provided() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="name is required"):
        dns_resolve_impl(client, name="   ")

    with pytest.raises(ValueError, match="server is required"):
        dns_resolve_impl(client, name="example.com", server="   ")


def test_dns_resolve_requires_address_in_router_response() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = {"ret": ""}
    client.isolated.return_value = isolated_client_mock(isolated_client)

    with pytest.raises(ValueError, match="did not return an address"):
        dns_resolve_impl(client, name="example.com")


def test_dns_resolve_propagates_router_errors() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.side_effect = RouterOSError("RouterOS command failed: dns timeout")
    client.isolated.return_value = isolated_client_mock(isolated_client)

    with pytest.raises(RouterOSError, match="dns timeout"):
        dns_resolve_impl(client, name="example.com")


def test_healthcheck_reports_separate_api_and_scp_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock(host="router.test")
    client.port = 8728
    client.use_ssl = False
    client.username = "api-user"
    client.password = "api-pass"
    client.print.return_value = [{"name": "lab-router"}]
    client.tls_session_info = lambda: None
    monkeypatch.setenv("MIKROTIK_USER", "api-user")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "api-pass")
    monkeypatch.setenv("MIKROTIK_SCP_USER", "scp-user")
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "scp-pass")

    class Settings:
        host = "files.router.test"
        port = 21

    downloader = Mock()
    downloader.check_connection.side_effect = RouterFileDownloadError("scp unavailable")

    monkeypatch.setattr(core, "load_file_transfer_settings", lambda host: Settings())
    monkeypatch.setattr(core, "SCPFileDownloader", lambda settings: downloader)

    result = healthcheck_impl(client)

    assert result["success"] is False
    assert result["status"] == "degraded"
    assert result["timestamp"].endswith("Z")
    assert result["config"]["api_host"] == "router.test"
    assert result["api"]["ok"] is True
    assert result["api"]["code"] == "api.ok"
    assert "certificate" not in result["api"]
    assert result["scp"] == {
        "ok": False,
        "status": "failed",
        "code": "scp.error",
        "message": "scp unavailable",
        "host": "files.router.test",
        "port": 21,
        "duration_ms": result["scp"]["duration_ms"],
    }
    assert isinstance(result["scp"]["duration_ms"], int)


def test_healthcheck_marks_api_failure_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock(host="router.test")
    client.port = 8729
    client.use_ssl = True
    client.username = "api-user"
    client.password = "api-pass"
    client.print.side_effect = RouterOSError("api unavailable")
    client.tls_session_info = lambda: {"subject": "commonName=Router"}
    monkeypatch.setenv("MIKROTIK_USER", "api-user")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "api-pass")
    monkeypatch.setenv("MIKROTIK_SCP_USER", "scp-user")
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "scp-pass")

    class Settings:
        host = "files.router.test"
        port = 21

    downloader = Mock()
    downloader.check_connection.return_value = {
        "working_directory": "/",
        "listing_count": 1,
        "listing_sample": ["backups"],
            "operation": "normalize+listdir_attr",
    }
    monkeypatch.setattr(core, "load_file_transfer_settings", lambda host: Settings())
    monkeypatch.setattr(core, "SCPFileDownloader", lambda settings: downloader)

    result = healthcheck_impl(client)

    assert result["success"] is False
    assert result["status"] == "degraded"
    assert result["api"] == {
        "ok": False,
        "status": "failed",
        "code": "api.error",
        "message": "api unavailable",
        "host": "router.test",
        "port": 8729,
        "tls": True,
        "duration_ms": result["api"]["duration_ms"],
    }
    assert result["scp"] == {
        "ok": True,
        "status": "ok",
        "code": "scp.ok",
        "message": "SCP login and directory probe succeeded for files.router.test:21",
        "host": "files.router.test",
        "port": 21,
        "probe": {
            "working_directory": "/",
            "listing_count": 1,
            "listing_sample": ["backups"],
            "operation": "normalize+listdir_attr",
        },
        "duration_ms": result["scp"]["duration_ms"],
    }
    assert isinstance(result["api"]["duration_ms"], int)


def test_healthcheck_classifies_api_auth_and_scp_config_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    from mikrotik_mcp.client import RouterOSAuthError

    client = Mock(host="router.test")
    client.port = 8729
    client.use_ssl = True
    client.username = "wrong"
    client.password = "bad"
    client.print.side_effect = RouterOSAuthError("bad login")
    monkeypatch.setenv("MIKROTIK_USER", "wrong")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "bad")
    monkeypatch.delenv("MIKROTIK_SCP_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PASSWORD", raising=False)

    monkeypatch.setattr(core, "load_file_transfer_settings", Mock(side_effect=RuntimeError("must be set before downloading files")))

    result = healthcheck_impl(client)

    assert result["status"] == "failed"
    assert result["api"]["code"] == "api.auth_failed"
    assert result["scp"]["code"] == "scp.config_missing"


def test_interface_monitor_returns_first_record() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = [
        {"status": "running", "rx-bits-per-second": "1000000", "tx-bits-per-second": "250000"}
    ]
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = interface_monitor_impl(client, name="ether1")

    assert result == {"status": "running", "rx-bits-per-second": "1000000", "tx-bits-per-second": "250000"}
    isolated_client.run.assert_called_once_with(
        "/interface/monitor-traffic",
        attrs={"interface": "ether1", "once": True},
    )
    client.isolated.assert_called_once_with()


def test_interface_monitor_accepts_single_dict_result() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.return_value = {"status": "running"}
    client.isolated.return_value = isolated_client_mock(isolated_client)

    result = interface_monitor_impl(client, name="ether1")

    assert result == {"status": "running"}


def test_interface_monitor_validates_name_and_requires_result() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="name is required"):
        interface_monitor_impl(client, name="   ")

    isolated_client = Mock()
    isolated_client.run.return_value = []
    client.isolated.return_value = isolated_client_mock(isolated_client)

    with pytest.raises(ValueError, match="No interface monitor result returned"):
        interface_monitor_impl(client, name="ether1")


def test_interface_monitor_propagates_router_errors() -> None:
    client = Mock()
    isolated_client = Mock()
    isolated_client.run.side_effect = RouterOSError("RouterOS command failed: interface busy")
    client.isolated.return_value = isolated_client_mock(isolated_client)

    with pytest.raises(RouterOSError, match="interface busy"):
        interface_monitor_impl(client, name="ether1")


def test_system_resource_get_returns_single_record() -> None:
    client = Mock()
    client.print.return_value = [{"uptime": "1d2h", "version": "7.17"}]

    result = system_resource_get_impl(client)

    assert result == {"uptime": "1d2h", "version": "7.17"}
    client.print.assert_called_once_with("/system/resource", proplist=None, queries=None, attrs=None)


def test_system_identity_get_requires_single_record() -> None:
    client = Mock()
    client.print.return_value = []

    with pytest.raises(ValueError, match="No matching system identity found"):
        system_identity_get_impl(client)


def test_system_clock_get_requires_single_record_when_multiple_match() -> None:
    client = Mock()
    client.print.return_value = [{"time": "12:00:00"}, {"time": "12:00:01"}]

    with pytest.raises(ValueError, match="Multiple system clock records matched"):
        system_clock_get_impl(client)


def test_interface_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"name": "ether1", "running": "true"}]

    result = interface_list_impl(client, running_only=True, disabled=False)

    assert result == [{"name": "ether1", "running": "true"}]
    client.print.assert_called_once_with(
        "/interface",
        proplist=None,
        queries=["disabled=false", "running=true"],
        attrs=None,
    )


def test_interface_get_uses_name_locator() -> None:
    client = Mock()
    client.print.return_value = [{"name": "ether1"}]

    result = interface_get_impl(client, name="ether1")

    assert result == {"name": "ether1"}
    client.print.assert_called_once_with("/interface", proplist=None, queries=["name=ether1"], attrs=None)


def test_interface_get_requires_exactly_one_locator() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="Exactly one interface locator is required"):
        interface_get_impl(client)

    with pytest.raises(ValueError, match="Exactly one interface locator is required"):
        interface_get_impl(client, name="ether1", item_id="*1")


def test_bridge_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"name": "bridge1", "disabled": "false"}]

    result = bridge_list_impl(client, name="bridge1", disabled=False)

    assert result == [{"name": "bridge1", "disabled": "false"}]
    client.print.assert_called_once_with(
        "/interface/bridge",
        proplist=None,
        queries=["name=bridge1", "disabled=false"],
        attrs=None,
    )


def test_bridge_add_calls_client_with_attributes() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*7"}

    result = bridge_add_impl(client, attributes={"name": "bridge1", "vlan-filtering": True})

    assert result == {"ret": "*7"}
    client.add.assert_called_once_with("/interface/bridge", attrs={"name": "bridge1", "vlan-filtering": True})


def test_bridge_add_requires_attributes() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="attributes are required"):
        bridge_add_impl(client)


def test_bridge_remove_calls_client_with_item_id() -> None:
    client = Mock()
    client.remove.return_value = {"success": True}

    result = bridge_remove_impl(client, item_id="*5")

    assert result == {"success": True}
    client.remove.assert_called_once_with("/interface/bridge", "*5")


def test_bridge_port_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"bridge": "bridge1", "interface": "ether2"}]

    result = bridge_port_list_impl(client, bridge="bridge1", interface="ether2", disabled=False)

    assert result == [{"bridge": "bridge1", "interface": "ether2"}]
    client.print.assert_called_once_with(
        "/interface/bridge/port",
        proplist=None,
        queries=["bridge=bridge1", "interface=ether2", "disabled=false"],
        attrs=None,
    )


def test_bridge_port_add_calls_client_with_attributes() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*9"}

    result = bridge_port_add_impl(client, attributes={"bridge": "bridge1", "interface": "ether2"})

    assert result == {"ret": "*9"}
    client.add.assert_called_once_with("/interface/bridge/port", attrs={"bridge": "bridge1", "interface": "ether2"})


def test_bridge_port_add_requires_attributes() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="attributes are required"):
        bridge_port_add_impl(client)


def test_bridge_port_remove_calls_client_with_item_id() -> None:
    client = Mock()
    client.remove.return_value = {"success": True}

    result = bridge_port_remove_impl(client, item_id="*10")

    assert result == {"success": True}
    client.remove.assert_called_once_with("/interface/bridge/port", "*10")


def test_bridge_vlan_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"bridge": "bridge1", "vlan-ids": "10"}]

    result = bridge_vlan_list_impl(client, bridge="bridge1", vlan_ids="10", disabled=False)

    assert result == [{"bridge": "bridge1", "vlan-ids": "10"}]
    client.print.assert_called_once_with(
        "/interface/bridge/vlan",
        proplist=None,
        queries=["bridge=bridge1", "vlan-ids=10", "disabled=false"],
        attrs=None,
    )


def test_bridge_vlan_add_calls_client_with_attributes() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*11"}

    result = bridge_vlan_add_impl(
        client,
        attributes={"bridge": "bridge1", "vlan-ids": "10", "tagged": "bridge1,ether1"},
    )

    assert result == {"ret": "*11"}
    client.add.assert_called_once_with(
        "/interface/bridge/vlan",
        attrs={"bridge": "bridge1", "vlan-ids": "10", "tagged": "bridge1,ether1"},
    )


def test_bridge_vlan_add_requires_attributes() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="attributes are required"):
        bridge_vlan_add_impl(client)


def test_bridge_vlan_remove_calls_client_with_item_id() -> None:
    client = Mock()
    client.remove.return_value = {"success": True}

    result = bridge_vlan_remove_impl(client, item_id="*13")

    assert result == {"success": True}
    client.remove.assert_called_once_with("/interface/bridge/vlan", "*13")


def test_vlan_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"name": "vlan10", "interface": "bridge1"}]

    result = vlan_list_impl(client, name="vlan10", interface="bridge1", disabled=True)

    assert result == [{"name": "vlan10", "interface": "bridge1"}]
    client.print.assert_called_once_with(
        "/interface/vlan",
        proplist=None,
        queries=["name=vlan10", "interface=bridge1", "disabled=true"],
        attrs=None,
    )


def test_vlan_add_calls_client_with_attributes() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*12"}

    result = vlan_add_impl(client, attributes={"name": "vlan10", "interface": "bridge1", "vlan-id": 10})

    assert result == {"ret": "*12"}
    client.add.assert_called_once_with(
        "/interface/vlan",
        attrs={"name": "vlan10", "interface": "bridge1", "vlan-id": 10},
    )


def test_vlan_add_requires_attributes() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="attributes are required"):
        vlan_add_impl(client)


def test_vlan_remove_calls_client_with_item_id() -> None:
    client = Mock()
    client.remove.return_value = {"success": True}

    result = vlan_remove_impl(client, item_id="*14")

    assert result == {"success": True}
    client.remove.assert_called_once_with("/interface/vlan", "*14")


def test_firewall_filter_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"chain": "forward", "action": "drop"}]

    result = firewall_filter_list_impl(client, chain="forward", action="drop", disabled=False)

    assert result == [{"chain": "forward", "action": "drop"}]
    client.print.assert_called_once_with(
        "/ip/firewall/filter",
        proplist=None,
        queries=["chain=forward", "action=drop", "disabled=false"],
        attrs=None,
    )


def test_firewall_filter_add_calls_client_with_attributes() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*20"}

    result = firewall_filter_add_impl(client, attributes={"chain": "forward", "action": "accept"})

    assert result == {"ret": "*20"}
    client.add.assert_called_once_with("/ip/firewall/filter", attrs={"chain": "forward", "action": "accept"})


def test_firewall_filter_add_requires_attributes() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="attributes are required"):
        firewall_filter_add_impl(client)


def test_firewall_filter_set_calls_client_with_item_id_and_attributes() -> None:
    client = Mock()
    client.set.return_value = {"success": True}

    result = firewall_filter_set_impl(client, item_id="*21", attributes={"disabled": True})

    assert result == {"success": True}
    client.set.assert_called_once_with("/ip/firewall/filter", "*21", attrs={"disabled": True})


def test_firewall_filter_set_requires_attributes() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="attributes are required"):
        firewall_filter_set_impl(client, item_id="*21")


def test_firewall_filter_remove_calls_client_with_item_id() -> None:
    client = Mock()
    client.remove.return_value = {"success": True}

    result = firewall_filter_remove_impl(client, item_id="*22")

    assert result == {"success": True}
    client.remove.assert_called_once_with("/ip/firewall/filter", "*22")


def test_firewall_nat_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"chain": "srcnat", "action": "masquerade"}]

    result = firewall_nat_list_impl(client, chain="srcnat", action="masquerade", disabled=True)

    assert result == [{"chain": "srcnat", "action": "masquerade"}]
    client.print.assert_called_once_with(
        "/ip/firewall/nat",
        proplist=None,
        queries=["chain=srcnat", "action=masquerade", "disabled=true"],
        attrs=None,
    )


def test_firewall_nat_add_calls_client_with_attributes() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*23"}

    result = firewall_nat_add_impl(client, attributes={"chain": "srcnat", "action": "masquerade"})

    assert result == {"ret": "*23"}
    client.add.assert_called_once_with("/ip/firewall/nat", attrs={"chain": "srcnat", "action": "masquerade"})


def test_firewall_nat_add_requires_attributes() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="attributes are required"):
        firewall_nat_add_impl(client)


def test_firewall_nat_set_calls_client_with_item_id_and_attributes() -> None:
    client = Mock()
    client.set.return_value = {"success": True}

    result = firewall_nat_set_impl(client, item_id="*24", attributes={"disabled": False})

    assert result == {"success": True}
    client.set.assert_called_once_with("/ip/firewall/nat", "*24", attrs={"disabled": False})


def test_firewall_nat_set_requires_attributes() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="attributes are required"):
        firewall_nat_set_impl(client, item_id="*24")


def test_firewall_nat_remove_calls_client_with_item_id() -> None:
    client = Mock()
    client.remove.return_value = {"success": True}

    result = firewall_nat_remove_impl(client, item_id="*25")

    assert result == {"success": True}
    client.remove.assert_called_once_with("/ip/firewall/nat", "*25")


def test_firewall_rule_move_calls_expected_command() -> None:
    client = Mock()
    client.run.return_value = {"success": True}

    result = firewall_rule_move_impl(client, table="filter", item_id="*26", destination="0")

    assert result == {"success": True}
    client.run.assert_called_once_with("/ip/firewall/filter/move", attrs={".id": "*26", "destination": "0"})


def test_firewall_rule_move_rejects_invalid_table() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="table must be either 'filter' or 'nat'"):
        firewall_rule_move_impl(client, table="mangle", item_id="*26", destination="0")


def test_firewall_rule_move_requires_destination() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="destination is required"):
        firewall_rule_move_impl(client, table="nat", item_id="*26", destination="   ")


def test_firewall_rule_move_requires_item_id() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="item_id is required"):
        firewall_rule_move_impl(client, table="nat", item_id="   ", destination="0")


def test_firewall_address_list_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"list": "trusted", "address": "192.0.2.10"}]

    result = firewall_address_list_list_impl(
        client,
        list_name="trusted",
        address="192.0.2.10",
        disabled=False,
    )

    assert result == [{"list": "trusted", "address": "192.0.2.10"}]
    client.print.assert_called_once_with(
        "/ip/firewall/address-list",
        proplist=None,
        queries=["address=192.0.2.10", "disabled=false", "list=trusted"],
        attrs=None,
    )


def test_firewall_address_list_add_calls_client_with_attributes() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*27"}

    result = firewall_address_list_add_impl(client, attributes={"list": "trusted", "address": "192.0.2.10"})

    assert result == {"ret": "*27"}
    client.add.assert_called_once_with(
        "/ip/firewall/address-list",
        attrs={"list": "trusted", "address": "192.0.2.10"},
    )


def test_firewall_address_list_add_requires_attributes() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="attributes are required"):
        firewall_address_list_add_impl(client)


def test_firewall_address_list_remove_calls_client_with_item_id() -> None:
    client = Mock()
    client.remove.return_value = {"success": True}

    result = firewall_address_list_remove_impl(client, item_id="*28")

    assert result == {"success": True}
    client.remove.assert_called_once_with("/ip/firewall/address-list", "*28")


def test_ppp_active_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"name": "alice", "service": "pppoe"}]

    result = ppp_active_list_impl(client, service="pppoe", name="alice")

    assert result == [{"name": "alice", "service": "pppoe"}]
    client.print.assert_called_once_with(
        "/ppp/active",
        proplist=None,
        queries=["service=pppoe", "name=alice"],
        attrs=None,
    )


def test_ppp_secret_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"name": "alice", "disabled": "false"}]

    result = ppp_secret_list_impl(client, name="alice", service="pppoe", disabled=False)

    assert result == [{"name": "alice", "disabled": "false"}]
    client.print.assert_called_once_with(
        "/ppp/secret",
        proplist=None,
        queries=["name=alice", "service=pppoe", "disabled=false"],
        attrs=None,
    )


def test_ppp_secret_add_calls_client_with_attributes() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*29"}

    result = ppp_secret_add_impl(client, attributes={"name": "alice", "password": "secret", "service": "pppoe"})

    assert result == {"ret": "*29"}
    client.add.assert_called_once_with(
        "/ppp/secret",
        attrs={"name": "alice", "password": "secret", "service": "pppoe"},
    )


def test_ppp_secret_add_requires_name_and_password() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="name is required"):
        ppp_secret_add_impl(client, attributes={"password": "secret"})

    with pytest.raises(ValueError, match="password is required"):
        ppp_secret_add_impl(client, attributes={"name": "alice"})


def test_ppp_secret_remove_calls_client_with_item_id() -> None:
    client = Mock()
    client.remove.return_value = {"success": True}

    result = ppp_secret_remove_impl(client, item_id="*30")

    assert result == {"success": True}
    client.remove.assert_called_once_with("/ppp/secret", "*30")


def test_wireguard_interface_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"name": "wg0", "disabled": "false"}]

    result = wireguard_interface_list_impl(client, name="wg0", disabled=False)

    assert result == [{"name": "wg0", "disabled": "false"}]
    client.print.assert_called_once_with(
        "/interface/wireguard",
        proplist=None,
        queries=["name=wg0", "disabled=false"],
        attrs=None,
    )


def test_wireguard_interface_add_calls_client_with_attributes() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*31"}

    result = wireguard_interface_add_impl(client, attributes={"name": "wg0", "listen-port": 51820})

    assert result == {"ret": "*31"}
    client.add.assert_called_once_with(
        "/interface/wireguard",
        attrs={"name": "wg0", "listen-port": 51820},
    )


def test_wireguard_interface_add_requires_name() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="name is required"):
        wireguard_interface_add_impl(client, attributes={"listen-port": 51820})


def test_wireguard_peer_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"interface": "wg0", "disabled": "true"}]

    result = wireguard_peer_list_impl(client, interface="wg0", disabled=True)

    assert result == [{"interface": "wg0", "disabled": "true"}]
    client.print.assert_called_once_with(
        "/interface/wireguard/peers",
        proplist=None,
        queries=["interface=wg0", "disabled=true"],
        attrs=None,
    )


def test_wireguard_peer_add_calls_client_with_attributes() -> None:
    client = Mock()
    client.add.return_value = {"ret": "*32"}

    result = wireguard_peer_add_impl(
        client,
        attributes={"interface": "wg0", "public-key": "abc123", "allowed-address": "10.0.0.2/32"},
    )

    assert result == {"ret": "*32"}
    client.add.assert_called_once_with(
        "/interface/wireguard/peers",
        attrs={"interface": "wg0", "public-key": "abc123", "allowed-address": "10.0.0.2/32"},
    )


def test_wireguard_peer_add_requires_interface_and_public_key() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="interface is required"):
        wireguard_peer_add_impl(client, attributes={"public-key": "abc123"})

    with pytest.raises(ValueError, match="public-key is required"):
        wireguard_peer_add_impl(client, attributes={"interface": "wg0"})


def test_wireguard_peer_remove_calls_client_with_item_id() -> None:
    client = Mock()
    client.remove.return_value = {"success": True}

    result = wireguard_peer_remove_impl(client, item_id="*33")

    assert result == {"success": True}
    client.remove.assert_called_once_with("/interface/wireguard/peers", "*33")


def test_ip_address_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"address": "192.0.2.10/24"}]

    result = ip_address_list_impl(client, interface="bridge", disabled=True)

    assert result == [{"address": "192.0.2.10/24"}]
    client.print.assert_called_once_with(
        "/ip/address",
        proplist=None,
        queries=["interface=bridge", "disabled=true"],
        attrs=None,
    )


def test_ip_address_get_uses_item_id_locator() -> None:
    client = Mock()
    client.print.return_value = [{".id": "*4", "address": "192.0.2.10/24"}]

    result = ip_address_get_impl(client, item_id="*4")

    assert result == {".id": "*4", "address": "192.0.2.10/24"}
    client.print.assert_called_once_with("/ip/address", proplist=None, queries=[".id=*4"], attrs=None)


def test_ip_route_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"dst-address": "0.0.0.0/0"}]

    result = ip_route_list_impl(client, dst_address="0.0.0.0/0", disabled=False)

    assert result == [{"dst-address": "0.0.0.0/0"}]
    client.print.assert_called_once_with(
        "/ip/route",
        proplist=None,
        queries=["dst-address=0.0.0.0/0", "disabled=false"],
        attrs=None,
    )


def test_ip_route_get_requires_exactly_one_locator() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="Exactly one IP route locator is required"):
        ip_route_get_impl(client)


def test_dhcp_lease_list_builds_expected_queries() -> None:
    client = Mock()
    client.print.return_value = [{"address": "192.0.2.20", "status": "bound"}]

    result = dhcp_lease_list_impl(
        client,
        address="192.0.2.20",
        mac_address="00:11:22:33:44:55",
        active_only=True,
    )

    assert result == [{"address": "192.0.2.20", "status": "bound"}]
    client.print.assert_called_once_with(
        "/ip/dhcp-server/lease",
        proplist=None,
        queries=["address=192.0.2.20", "mac-address=00:11:22:33:44:55", "status=bound"],
        attrs=None,
    )


def test_dhcp_server_list_uses_expected_menu() -> None:
    client = Mock()
    client.print.return_value = [{"name": "dhcp1"}]

    assert dhcp_server_list_impl(client) == [{"name": "dhcp1"}]
    client.print.assert_called_once_with("/ip/dhcp-server", proplist=None, queries=None, attrs=None)


def test_dhcp_network_list_uses_expected_menu() -> None:
    client = Mock()
    client.print.return_value = [{"address": "192.0.2.0/24"}]

    assert dhcp_network_list_impl(client) == [{"address": "192.0.2.0/24"}]
    client.print.assert_called_once_with("/ip/dhcp-server/network", proplist=None, queries=None, attrs=None)


def test_dns_get_returns_single_record() -> None:
    client = Mock()
    client.print.return_value = [{"allow-remote-requests": "true", "servers": "1.1.1.1"}]

    result = dns_get_impl(client)

    assert result == {"allow-remote-requests": "true", "servers": "1.1.1.1"}
    client.print.assert_called_once_with("/ip/dns", proplist=None, queries=None, attrs=None)


def test_dns_set_calls_dns_set_command_with_normalized_attributes() -> None:
    client = Mock()
    client.run.return_value = {"success": True}

    result = dns_set_impl(
        client,
        servers=["1.1.1.1", " 8.8.8.8 "],
        allow_remote_requests=True,
        cache_size="2048KiB",
    )

    assert result == {"success": True}
    client.run.assert_called_once_with(
        "/ip/dns/set",
        attrs={
            "servers": "1.1.1.1,8.8.8.8",
            "allow-remote-requests": True,
            "cache-size": "2048KiB",
        },
    )


def test_dns_set_requires_at_least_one_change() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="At least one DNS setting must be provided"):
        dns_set_impl(client)


def test_file_list_filters_by_directory_after_router_query() -> None:
    client = Mock()
    client.print.return_value = [
        {"name": "backups", "type": "directory"},
        {"name": "backups/router.backup", "type": "backup"},
        {"name": "backups/router.rsc", "type": "script"},
        {"name": "logs/router.rsc", "type": "script"},
    ]

    result = file_list_impl(client, directory="backups", file_type="script")

    assert result == [{"name": "backups/router.rsc", "type": "script"}]
    client.print.assert_called_once_with("/file", proplist=None, queries=["type=script"], attrs=None)


def test_file_list_rejects_empty_directory_filter() -> None:
    client = Mock()
    client.print.return_value = []

    with pytest.raises(ValueError, match="directory must not be empty"):
        file_list_impl(client, directory="   ")


def test_system_backup_save_runs_router_command_and_returns_stable_shape() -> None:
    client = Mock()
    client.run.return_value = {"success": True}

    result = system_backup_save_impl(client, name="backups/nightly.backup")

    assert result == {
        "success": True,
        "name": "backups/nightly",
        "path": "backups/nightly.backup",
    }
    client.run.assert_called_once_with("/system/backup/save", attrs={"name": "backups/nightly"})


def test_system_backup_save_requires_non_empty_name() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="name is required"):
        system_backup_save_impl(client, name="   ")


def test_system_export_runs_router_command_with_optional_flags() -> None:
    client = Mock()
    client.run.return_value = {"success": True}

    result = system_export_impl(client, name="backups/nightly.rsc", include_sensitive=True, compact=True)

    assert result == {
        "success": True,
        "name": "backups/nightly",
        "path": "backups/nightly.rsc",
        "include_sensitive": True,
        "compact": True,
    }
    client.run.assert_called_once_with(
        "/export",
        attrs={
            "file": "backups/nightly",
            "show-sensitive": "",
            "compact": "",
        },
    )


def test_system_export_rejects_name_ending_in_directory_separator() -> None:
    client = Mock()

    with pytest.raises(ValueError, match="name must not end with '/'"):
        system_export_impl(client, name="backups/")


def test_file_download_uses_explicit_local_path(tmp_path: Path) -> None:
    client = Mock(host="router.test")
    downloader = RecordingDownloader()
    destination = tmp_path / "artifacts" / "router.backup"

    result = file_download_impl(
        client,
        router_path="backups/router.backup",
        local_path=str(destination),
        downloader=downloader,
    )

    assert result == {
        "success": True,
        "router_path": "backups/router.backup",
        "local_path": str(destination),
    }
    assert downloader.calls == [("backups/router.backup", destination)]


def test_file_download_defaults_to_local_backups_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock(host="router.test")
    downloader = RecordingDownloader()
    monkeypatch.setattr(file_tool_impls, "workspace_root", lambda: tmp_path)
    router_path = "backups/pytest-unique-router.backup"

    result = file_download_impl(client, router_path=router_path, downloader=downloader)

    local_path = Path(str(result["local_path"]))
    assert result["success"] is True
    assert result["router_path"] == router_path
    assert local_path.parent == tmp_path / "backups"
    assert local_path.name.startswith("pytest-unique-router")
    assert local_path.suffix == ".backup"
    assert downloader.calls == [(router_path, local_path)]


def test_file_download_resolves_relative_local_path_from_workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock(host="router.test")
    downloader = RecordingDownloader()
    monkeypatch.setattr(file_tool_impls, "workspace_root", lambda: tmp_path)

    result = file_download_impl(
        client,
        router_path="backups/router.backup",
        local_path="backups/custom/router.backup",
        downloader=downloader,
    )

    expected_path = tmp_path / "backups" / "custom" / "router.backup"
    assert result == {
        "success": True,
        "router_path": "backups/router.backup",
        "local_path": str(expected_path),
    }
    assert downloader.calls == [("backups/router.backup", expected_path)]


def test_system_backup_collect_creates_and_downloads_both_artifacts(tmp_path: Path) -> None:
    client = Mock(host="router.test")
    client.add.return_value = {"success": True}
    client.run.return_value = {"success": True}
    downloader = RecordingDownloader()

    def print_side_effect(menu: str, proplist=None, queries=None, attrs=None):
        assert menu == "/file"
        if queries == ["name=backups"]:
            return []
        backup_name = client.run.call_args_list[0].kwargs["attrs"]["name"]
        export_name = client.run.call_args_list[1].kwargs["attrs"]["file"]
        return [
            {"name": f"{backup_name}.backup", "type": "backup"},
            {"name": f"{export_name}.rsc", "type": "script"},
        ]

    client.print.side_effect = print_side_effect

    result = system_backup_collect_impl(
        client,
        name_prefix="nightly",
        include_sensitive=True,
        compact=True,
        local_dir=str(tmp_path / "artifacts"),
        downloader=downloader,
    )

    assert result["success"] is True
    assert result["router_backup_path"].startswith("backups/nightly-")
    assert result["router_backup_path"].endswith(".backup")
    assert result["router_export_path"].startswith("backups/nightly-")
    assert result["router_export_path"].endswith(".rsc")
    assert result["local_backup_path"].startswith(str(tmp_path / "artifacts" / "router-test-nightly-"))
    assert result["local_backup_path"].endswith(".backup")
    assert result["local_export_path"].startswith(str(tmp_path / "artifacts" / "router-test-nightly-"))
    assert result["local_export_path"].endswith(".rsc")
    assert downloader.calls == [
        (result["router_backup_path"], Path(result["local_backup_path"])),
        (result["router_export_path"], Path(result["local_export_path"])),
    ]
    client.add.assert_called_once_with("/file", attrs={"name": "backups", "type": "directory"})
    assert client.run.call_count == 2
    client.run.assert_any_call("/system/backup/save", attrs={"name": result["router_backup_path"][:-7]})
    client.run.assert_any_call(
        "/export",
        attrs={
            "file": result["router_export_path"][:-4],
            "show-sensitive": "",
            "compact": "",
        },
    )


def test_system_backup_collect_resolves_relative_local_dir_from_workspace_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = Mock(host="router.test")
    client.run.return_value = {"success": True}
    downloader = RecordingDownloader()
    monkeypatch.setattr(file_tool_impls, "workspace_root", lambda: tmp_path)
    monkeypatch.setattr(server_helpers, "workspace_root", lambda: tmp_path)

    def print_side_effect(menu: str, proplist=None, queries=None, attrs=None):
        assert menu == "/file"
        if queries == ["name=backups"]:
            return [{"name": "backups", "type": "directory"}]
        backup_name = client.run.call_args_list[0].kwargs["attrs"]["name"]
        export_name = client.run.call_args_list[1].kwargs["attrs"]["file"]
        return [
            {"name": f"{backup_name}.backup", "type": "backup"},
            {"name": f"{export_name}.rsc", "type": "script"},
        ]

    client.print.side_effect = print_side_effect

    result = system_backup_collect_impl(client, name_prefix="nightly", local_dir="backups", downloader=downloader)

    assert result["local_backup_path"].startswith(str(tmp_path / "backups" / "router-test-nightly-"))
    assert result["local_export_path"].startswith(str(tmp_path / "backups" / "router-test-nightly-"))


def test_system_backup_collect_skips_directory_creation_when_backups_exists(tmp_path: Path) -> None:
    client = Mock(host="router.test")
    client.run.return_value = {"success": True}

    def print_side_effect(menu: str, proplist=None, queries=None, attrs=None):
        assert menu == "/file"
        if queries == ["name=backups"]:
            return [{"name": "backups", "type": "directory"}]
        backup_name = client.run.call_args_list[0].kwargs["attrs"]["name"]
        export_name = client.run.call_args_list[1].kwargs["attrs"]["file"]
        return [
            {"name": f"{backup_name}.backup", "type": "backup"},
            {"name": f"{export_name}.rsc", "type": "script"},
        ]

    client.print.side_effect = print_side_effect

    system_backup_collect_impl(client, local_dir=str(tmp_path), downloader=RecordingDownloader())

    client.add.assert_not_called()


def test_system_backup_collect_stops_when_export_creation_fails(tmp_path: Path) -> None:
    client = Mock(host="router.test")
    client.print.return_value = [{"name": "backups", "type": "directory"}]
    client.run.side_effect = [{"success": True}, RuntimeError("disk full")]
    downloader = RecordingDownloader()

    with pytest.raises(RuntimeError, match="export creation failed before downloads started"):
        system_backup_collect_impl(client, local_dir=str(tmp_path), downloader=downloader)

    assert downloader.calls == []


def test_system_backup_collect_reports_download_failure_with_paths(tmp_path: Path) -> None:
    client = Mock(host="router.test")
    client.run.return_value = {"success": True}
    downloader = RecordingDownloader(fail_on_call=2)

    def print_side_effect(menu: str, proplist=None, queries=None, attrs=None):
        assert menu == "/file"
        if queries == ["name=backups"]:
            return [{"name": "backups", "type": "directory"}]
        backup_name = client.run.call_args_list[0].kwargs["attrs"]["name"]
        export_name = client.run.call_args_list[1].kwargs["attrs"]["file"]
        return [
            {"name": f"{backup_name}.backup", "type": "backup"},
            {"name": f"{export_name}.rsc", "type": "script"},
        ]

    client.print.side_effect = print_side_effect

    with pytest.raises(RuntimeError, match="local download failed"):
        system_backup_collect_impl(client, local_dir=str(tmp_path), downloader=downloader)

    assert len(downloader.calls) == 2
