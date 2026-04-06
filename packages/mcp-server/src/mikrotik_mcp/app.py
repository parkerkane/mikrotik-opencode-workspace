from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import RouterOSClient
from .tool_impls import access, core, files, layer2, security


def _register_core_tools(app: FastMCP, client: RouterOSClient) -> None:
    @app.tool(
        description="Run a generic RouterOS print command and optionally apply jq to the normalized array response.",
    )
    def resource_print(
        menu: str,
        proplist: list[str] | None = None,
        queries: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
        jq_filter: str | None = None,
    ) -> Any:
        return core.resource_print_impl(
            client,
            menu=menu,
            proplist=proplist,
            queries=queries,
            attributes=attributes,
            jq_filter=jq_filter,
        )

    @app.tool(description="Run a generic RouterOS add command for a menu path.")
    def resource_add(
        menu: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return core.resource_add_impl(client, menu=menu, attributes=attributes)

    @app.tool(description="Run a generic RouterOS set command for a menu path and item id.")
    def resource_set(
        menu: str,
        item_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return core.resource_set_impl(client, menu=menu, item_id=item_id, attributes=attributes)

    @app.tool(description="Run a generic RouterOS remove command for a menu path and item id.")
    def resource_remove(
        menu: str,
        item_id: str,
    ) -> dict[str, str] | dict[str, bool]:
        return core.resource_remove_impl(client, menu=menu, item_id=item_id)

    @app.tool(description="Run a generic RouterOS command path and return normalized output.")
    def command_run(
        command: str,
        attributes: dict[str, Any] | None = None,
        queries: list[str] | None = None,
    ) -> Any:
        return core.command_run_impl(client, command=command, attributes=attributes, queries=queries)

    @app.tool(description="Listen for changes on a RouterOS menu and return a bounded batch of events.")
    def resource_listen(
        menu: str,
        proplist: list[str] | None = None,
        queries: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
        tag: str | None = None,
        max_events: int = 10,
    ) -> dict[str, Any]:
        return core.resource_listen_impl(
            client,
            menu=menu,
            proplist=proplist,
            queries=queries,
            attributes=attributes,
            tag=tag,
            max_events=max_events,
        )

    @app.tool(description="Cancel a tagged long-running RouterOS API command.")
    def command_cancel(tag: str) -> dict[str, str] | dict[str, bool]:
        return core.command_cancel_impl(client, tag=tag)

    @app.tool(description="Run a bounded ping from the router and return per-probe results.")
    def tool_ping(
        address: str,
        count: int = 4,
        interval: str | None = None,
        interface: str | None = None,
        packet_size: int | None = None,
    ) -> list[dict[str, str]]:
        return core.tool_ping_impl(
            client,
            address=address,
            count=count,
            interval=interval,
            interface=interface,
            packet_size=packet_size,
        )

    @app.tool(description="Get RouterOS system resource details.")
    def system_resource_get() -> dict[str, str]:
        return core.system_resource_get_impl(client)

    @app.tool(description="Get the RouterOS system identity.")
    def system_identity_get() -> dict[str, str]:
        return core.system_identity_get_impl(client)

    @app.tool(description="Get the RouterOS system clock settings.")
    def system_clock_get() -> dict[str, str]:
        return core.system_clock_get_impl(client)

    @app.tool(description="List network interfaces with optional status filters.")
    def interface_list(
        running_only: bool = False,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return core.interface_list_impl(client, running_only=running_only, disabled=disabled)

    @app.tool(description="Get one interface by name or RouterOS item id.")
    def interface_get(
        name: str | None = None,
        item_id: str | None = None,
    ) -> dict[str, str]:
        return core.interface_get_impl(client, name=name, item_id=item_id)

    @app.tool(description="List IP addresses with optional interface and disabled filters.")
    def ip_address_list(
        interface: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return core.ip_address_list_impl(client, interface=interface, disabled=disabled)

    @app.tool(description="Get one IP address by address or RouterOS item id.")
    def ip_address_get(
        address: str | None = None,
        item_id: str | None = None,
    ) -> dict[str, str]:
        return core.ip_address_get_impl(client, address=address, item_id=item_id)

    @app.tool(description="List IP routes with optional destination and disabled filters.")
    def ip_route_list(
        dst_address: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return core.ip_route_list_impl(client, dst_address=dst_address, disabled=disabled)

    @app.tool(description="Get one IP route by destination or RouterOS item id.")
    def ip_route_get(
        dst_address: str | None = None,
        item_id: str | None = None,
    ) -> dict[str, str]:
        return core.ip_route_get_impl(client, dst_address=dst_address, item_id=item_id)

    @app.tool(description="List DHCP leases with optional address, MAC, and active filters.")
    def dhcp_lease_list(
        address: str | None = None,
        mac_address: str | None = None,
        active_only: bool = False,
    ) -> list[dict[str, str]]:
        return core.dhcp_lease_list_impl(client, address=address, mac_address=mac_address, active_only=active_only)

    @app.tool(description="List configured DHCP servers.")
    def dhcp_server_list() -> list[dict[str, str]]:
        return core.dhcp_server_list_impl(client)

    @app.tool(description="List configured DHCP networks.")
    def dhcp_network_list() -> list[dict[str, str]]:
        return core.dhcp_network_list_impl(client)

    @app.tool(description="Get RouterOS DNS settings.")
    def dns_get() -> dict[str, str]:
        return core.dns_get_impl(client)

    @app.tool(description="Update RouterOS DNS settings.")
    def dns_set(
        servers: list[str] | None = None,
        allow_remote_requests: bool | None = None,
        cache_size: str | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return core.dns_set_impl(
            client,
            servers=servers,
            allow_remote_requests=allow_remote_requests,
            cache_size=cache_size,
        )


def _register_layer2_tools(app: FastMCP, client: RouterOSClient) -> None:
    @app.tool(description="List bridges with optional name and disabled filters.")
    def bridge_list(
        name: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return layer2.bridge_list_impl(client, name=name, disabled=disabled)

    @app.tool(description="Create a bridge using RouterOS bridge attributes.")
    def bridge_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return layer2.bridge_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a bridge by RouterOS item id.")
    def bridge_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return layer2.bridge_remove_impl(client, item_id=item_id)

    @app.tool(description="List bridge ports with optional bridge, interface, and disabled filters.")
    def bridge_port_list(
        bridge: str | None = None,
        interface: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return layer2.bridge_port_list_impl(client, bridge=bridge, interface=interface, disabled=disabled)

    @app.tool(description="Add a bridge port using RouterOS bridge port attributes.")
    def bridge_port_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return layer2.bridge_port_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a bridge port by RouterOS item id.")
    def bridge_port_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return layer2.bridge_port_remove_impl(client, item_id=item_id)

    @app.tool(description="List bridge VLAN entries with optional bridge, VLAN ID, and disabled filters.")
    def bridge_vlan_list(
        bridge: str | None = None,
        vlan_ids: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return layer2.bridge_vlan_list_impl(client, bridge=bridge, vlan_ids=vlan_ids, disabled=disabled)

    @app.tool(description="Add a bridge VLAN entry using RouterOS bridge VLAN attributes.")
    def bridge_vlan_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return layer2.bridge_vlan_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a bridge VLAN entry by RouterOS item id.")
    def bridge_vlan_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return layer2.bridge_vlan_remove_impl(client, item_id=item_id)

    @app.tool(description="List VLAN interfaces with optional name, parent interface, and disabled filters.")
    def vlan_list(
        name: str | None = None,
        interface: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return layer2.vlan_list_impl(client, name=name, interface=interface, disabled=disabled)

    @app.tool(description="Create a VLAN interface using RouterOS VLAN attributes.")
    def vlan_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return layer2.vlan_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a VLAN interface by RouterOS item id.")
    def vlan_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return layer2.vlan_remove_impl(client, item_id=item_id)


def _register_security_tools(app: FastMCP, client: RouterOSClient) -> None:
    @app.tool(description="List firewall filter rules with optional chain, action, and disabled filters.")
    def firewall_filter_list(
        chain: str | None = None,
        action: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return security.firewall_filter_list_impl(client, chain=chain, action=action, disabled=disabled)

    @app.tool(description="Add a firewall filter rule using RouterOS firewall attributes.")
    def firewall_filter_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return security.firewall_filter_add_impl(client, attributes=attributes)

    @app.tool(description="Update a firewall filter rule by RouterOS item id.")
    def firewall_filter_set(
        item_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return security.firewall_filter_set_impl(client, item_id=item_id, attributes=attributes)

    @app.tool(description="Remove a firewall filter rule by RouterOS item id.")
    def firewall_filter_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return security.firewall_filter_remove_impl(client, item_id=item_id)

    @app.tool(description="List firewall NAT rules with optional chain, action, and disabled filters.")
    def firewall_nat_list(
        chain: str | None = None,
        action: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return security.firewall_nat_list_impl(client, chain=chain, action=action, disabled=disabled)

    @app.tool(description="Add a firewall NAT rule using RouterOS firewall attributes.")
    def firewall_nat_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return security.firewall_nat_add_impl(client, attributes=attributes)

    @app.tool(description="Update a firewall NAT rule by RouterOS item id.")
    def firewall_nat_set(
        item_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return security.firewall_nat_set_impl(client, item_id=item_id, attributes=attributes)

    @app.tool(description="Remove a firewall NAT rule by RouterOS item id.")
    def firewall_nat_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return security.firewall_nat_remove_impl(client, item_id=item_id)

    @app.tool(description="Move a firewall filter or NAT rule to a new destination position or item id.")
    def firewall_rule_move(
        table: str,
        item_id: str,
        destination: str,
    ) -> dict[str, str] | dict[str, bool]:
        return security.firewall_rule_move_impl(client, table=table, item_id=item_id, destination=destination)

    @app.tool(description="List firewall address-list entries with optional list, address, and disabled filters.")
    def firewall_address_list_list(
        list_name: str | None = None,
        address: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return security.firewall_address_list_list_impl(client, list_name=list_name, address=address, disabled=disabled)

    @app.tool(description="Add a firewall address-list entry using RouterOS firewall attributes.")
    def firewall_address_list_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return security.firewall_address_list_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a firewall address-list entry by RouterOS item id.")
    def firewall_address_list_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return security.firewall_address_list_remove_impl(client, item_id=item_id)


def _register_access_tools(app: FastMCP, client: RouterOSClient) -> None:
    @app.tool(description="List active PPP sessions with optional service and name filters.")
    def ppp_active_list(
        service: str | None = None,
        name: str | None = None,
    ) -> list[dict[str, str]]:
        return access.ppp_active_list_impl(client, service=service, name=name)

    @app.tool(description="List PPP secrets with optional name, service, and disabled filters.")
    def ppp_secret_list(
        name: str | None = None,
        service: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return access.ppp_secret_list_impl(client, name=name, service=service, disabled=disabled)

    @app.tool(description="Create a PPP secret using RouterOS PPP secret attributes.")
    def ppp_secret_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return access.ppp_secret_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a PPP secret by RouterOS item id.")
    def ppp_secret_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return access.ppp_secret_remove_impl(client, item_id=item_id)

    @app.tool(description="List WireGuard interfaces with optional name and disabled filters.")
    def wireguard_interface_list(
        name: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return access.wireguard_interface_list_impl(client, name=name, disabled=disabled)

    @app.tool(description="Create a WireGuard interface using RouterOS WireGuard attributes.")
    def wireguard_interface_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return access.wireguard_interface_add_impl(client, attributes=attributes)

    @app.tool(description="List WireGuard peers with optional interface and disabled filters.")
    def wireguard_peer_list(
        interface: str | None = None,
        disabled: bool | None = None,
    ) -> list[dict[str, str]]:
        return access.wireguard_peer_list_impl(client, interface=interface, disabled=disabled)

    @app.tool(description="Create a WireGuard peer using RouterOS peer attributes.")
    def wireguard_peer_add(
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, str] | dict[str, bool]:
        return access.wireguard_peer_add_impl(client, attributes=attributes)

    @app.tool(description="Remove a WireGuard peer by RouterOS item id.")
    def wireguard_peer_remove(item_id: str) -> dict[str, str] | dict[str, bool]:
        return access.wireguard_peer_remove_impl(client, item_id=item_id)


def _register_file_tools(app: FastMCP, client: RouterOSClient) -> None:
    @app.tool(description="List router files with optional directory, name, and type filters.")
    def file_list(
        directory: str | None = None,
        name: str | None = None,
        file_type: str | None = None,
    ) -> list[dict[str, str]]:
        return files.file_list_impl(client, directory=directory, name=name, file_type=file_type)

    @app.tool(description="Create a RouterOS backup file on the router.")
    def system_backup_save(name: str) -> dict[str, str | bool]:
        return files.system_backup_save_impl(client, name=name)

    @app.tool(description="Export RouterOS configuration to an .rsc file on the router.")
    def system_export(
        name: str,
        include_sensitive: bool = False,
        compact: bool = False,
    ) -> dict[str, str | bool]:
        return files.system_export_impl(client, name=name, include_sensitive=include_sensitive, compact=compact)

    @app.tool(description="Download a router file into the local workspace.")
    def file_download(
        router_path: str,
        local_path: str | None = None,
    ) -> dict[str, str | bool]:
        return files.file_download_impl(client, router_path=router_path, local_path=local_path)

    @app.tool(description="Create router backup artifacts and download them into the local workspace.")
    def system_backup_collect(
        name_prefix: str | None = None,
        include_sensitive: bool = False,
        compact: bool = False,
        local_dir: str | None = None,
    ) -> dict[str, str | bool]:
        return files.system_backup_collect_impl(
            client,
            name_prefix=name_prefix,
            include_sensitive=include_sensitive,
            compact=compact,
            local_dir=local_dir,
        )


def create_app(client: RouterOSClient) -> FastMCP:
    app = FastMCP("mikrotik")
    _register_core_tools(app, client)
    _register_layer2_tools(app, client)
    _register_security_tools(app, client)
    _register_access_tools(app, client)
    _register_file_tools(app, client)
    return app
