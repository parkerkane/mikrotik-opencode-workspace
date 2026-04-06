from __future__ import annotations

from unittest.mock import Mock

import pytest

from mikrotik_mcp.server import (
    command_run_impl,
    dhcp_lease_list_impl,
    dhcp_network_list_impl,
    dhcp_server_list_impl,
    dns_get_impl,
    dns_set_impl,
    interface_get_impl,
    interface_list_impl,
    ip_address_get_impl,
    ip_address_list_impl,
    ip_route_get_impl,
    ip_route_list_impl,
    resource_add_impl,
    resource_print_impl,
    resource_remove_impl,
    resource_set_impl,
    system_clock_get_impl,
    system_identity_get_impl,
    system_resource_get_impl,
)


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
