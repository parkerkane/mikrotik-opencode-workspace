from __future__ import annotations

from unittest.mock import Mock

import pytest

from mikrotik_mcp.server import (
    command_run_impl,
    resource_add_impl,
    resource_print_impl,
    resource_remove_impl,
    resource_set_impl,
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
