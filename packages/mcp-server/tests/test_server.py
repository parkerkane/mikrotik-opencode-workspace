from __future__ import annotations

from unittest.mock import Mock

import pytest

from mikrotik_mcp.server import resource_print_impl


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
