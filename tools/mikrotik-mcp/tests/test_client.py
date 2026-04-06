from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock

import pytest

from mikrotik_mcp.client import RouterOSClient, RouterOSFatalError, RouterOSError, encode_length, decode_length, parse_reply_sentences


@pytest.mark.parametrize(
    ("length", "expected"),
    [
        (0, b"\x00"),
        (127, b"\x7f"),
        (128, b"\x80\x80"),
        (16383, b"\xbf\xff"),
        (16384, b"\xc0\x40\x00"),
    ],
)
def test_encode_length_matches_routeros_prefixes(length: int, expected: bytes) -> None:
    assert encode_length(length) == expected


@pytest.mark.parametrize("length", [0, 1, 127, 128, 4096, 16383, 16384, 70000])
def test_decode_length_round_trip(length: int) -> None:
    assert decode_length(BytesIO(encode_length(length))) == length


def test_parse_reply_sentences_collects_records_and_done() -> None:
    reply = parse_reply_sentences(
        [
            ["!re", "=.id=*1", "=name=ether1", "=running=true"],
            ["!re", "=.id=*2", "=name=ether2", "=running=false"],
            ["!done", "=ret=ok"],
        ]
    )

    assert reply.records == [
        {".id": "*1", "name": "ether1", "running": "true"},
        {".id": "*2", "name": "ether2", "running": "false"},
    ]
    assert reply.done == {"ret": "ok"}
    assert reply.traps == []
    assert reply.fatal is None


def test_parse_reply_sentences_preserves_tag_metadata() -> None:
    reply = parse_reply_sentences(
        [
            ["!re", "=.tag=listen-1", "=name=ether1"],
            ["!done", "=.tag=listen-1", "=ret=ok"],
        ]
    )

    assert reply.tag == "listen-1"
    assert reply.records == [{".tag": "listen-1", "name": "ether1"}]
    assert reply.done == {".tag": "listen-1", "ret": "ok"}


def test_print_builds_sentence_and_returns_records(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(
        client.encode_sentence(["!re", "=.id=*1", "=name=ether1", "=disabled=false"])
    )
    fake_socket.response_bytes.extend(client.encode_sentence(["!done"]))
    client._socket = fake_socket

    records = client.print(
        "/interface",
        proplist=["name", "disabled"],
        queries=["disabled=false", "?#|"],
        attrs={"detail": True},
    )

    assert records == [{".id": "*1", "name": "ether1", "disabled": "false"}]
    assert bytes(fake_socket.sent) == client.encode_sentence(
        [
            "/interface/print",
            "=.proplist=name,disabled",
            "=detail=true",
            "?disabled=false",
            "?#|",
        ]
    )


def test_login_trap_raises_credential_error(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(
        client.encode_sentence(["!trap", "=message=invalid user name or password"])
    )
    fake_socket.response_bytes.extend(client.encode_sentence(["!done"]))
    client._socket = fake_socket

    with pytest.raises(Exception, match="RouterOS login failed"):
        client.login()


def test_add_builds_sentence_and_returns_done_payload(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!done", "=ret=*3"]))
    client._socket = fake_socket

    result = client.add("/ip/address", attrs={"address": "192.0.2.10/24", "interface": "ether1", "disabled": False})

    assert result == {"ret": "*3"}
    assert bytes(fake_socket.sent) == client.encode_sentence(
        [
            "/ip/address/add",
            "=address=192.0.2.10/24",
            "=interface=ether1",
            "=disabled=false",
        ]
    )


def test_set_builds_sentence_with_explicit_item_id(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!done"]))
    client._socket = fake_socket

    result = client.set("/ip/address", "*3", attrs={"disabled": True})

    assert result == {"success": True}
    assert bytes(fake_socket.sent) == client.encode_sentence(
        [
            "/ip/address/set",
            "=.id=*3",
            "=disabled=true",
        ]
    )


def test_remove_builds_sentence_with_explicit_item_id(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!empty"]))
    fake_socket.response_bytes.extend(client.encode_sentence(["!done"]))
    client._socket = fake_socket

    result = client.remove("/ip/address", "*3")

    assert result == {"success": True, "empty": True}
    assert bytes(fake_socket.sent) == client.encode_sentence(
        [
            "/ip/address/remove",
            "=.id=*3",
        ]
    )


def test_command_run_returns_records_when_reply_has_re_data(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!re", "=host=192.0.2.1", "=status=reachable"]))
    fake_socket.response_bytes.extend(client.encode_sentence(["!done", "=ret=ok"]))
    client._socket = fake_socket

    result = client.run("/tool/ping", attrs={"address": "192.0.2.1", "count": 1}, queries=["status=reachable"])

    assert result == [{"host": "192.0.2.1", "status": "reachable"}]
    assert bytes(fake_socket.sent) == client.encode_sentence(
        [
            "/tool/ping",
            "=address=192.0.2.1",
            "=count=1",
            "?status=reachable",
        ]
    )


def test_command_run_returns_done_payload_without_records(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!done", "=ret=ok"]))
    client._socket = fake_socket

    result = client.run("system/reboot")

    assert result == {"ret": "ok"}


def test_command_run_supports_explicit_tag(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!done", "=.tag=ping-1", "=ret=ok"]))
    client._socket = fake_socket

    result = client.run("tool/ping", attrs={"address": "192.0.2.1"}, tag="ping-1")

    assert result == {".tag": "ping-1", "ret": "ok"}
    assert bytes(fake_socket.sent) == client.encode_sentence(
        [
            "/tool/ping",
            "=address=192.0.2.1",
            "=.tag=ping-1",
        ]
    )


def test_listen_returns_bounded_records_and_cancels_by_tag(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!re", "=.tag=listen-1", "=name=ether1"]))
    fake_socket.response_bytes.extend(client.encode_sentence(["!re", "=.tag=listen-1", "=name=ether2"]))
    fake_socket.response_bytes.extend(client.encode_sentence(["!done", "=.tag=listen-1-cancel", "=ret=interrupted"]))
    fake_socket.response_bytes.extend(client.encode_sentence(["!done", "=.tag=listen-1"]))
    client._socket = fake_socket

    result = client.listen("/interface", queries=["running=true"], tag="listen-1", max_events=2)

    assert result.tag == "listen-1"
    assert result.records == [
        {".tag": "listen-1", "name": "ether1"},
        {".tag": "listen-1", "name": "ether2"},
    ]
    assert result.cancelled is True
    assert result.limit_reached is True
    assert result.cancel_done == {".tag": "listen-1-cancel", "ret": "interrupted"}
    assert bytes(fake_socket.sent) == client.encode_sentence(
        [
            "/interface/listen",
            "?running=true",
            "=.tag=listen-1",
        ]
    ) + client.encode_sentence(
        [
            "/cancel",
            "=tag=listen-1",
            "=.tag=listen-1-cancel",
        ]
    )


def test_listen_requires_positive_max_events(client: RouterOSClient) -> None:
    with pytest.raises(ValueError, match="max_events must be at least 1"):
        client.listen("/interface", max_events=0)


def test_listen_generates_tag_when_not_provided(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!re", "=.tag=listen-generated", "=name=ether1"]))
    fake_socket.response_bytes.extend(client.encode_sentence(["!done", "=.tag=listen-generated-cancel", "=ret=interrupted"]))
    fake_socket.response_bytes.extend(client.encode_sentence(["!done", "=.tag=listen-generated"]))
    client._socket = fake_socket
    client._generate_tag = Mock(return_value="listen-generated")

    result = client.listen("/interface", max_events=1)

    assert result.tag == "listen-generated"
    assert result.cancel_done == {".tag": "listen-generated-cancel", "ret": "interrupted"}
    assert bytes(fake_socket.sent) == client.encode_sentence(
        [
            "/interface/listen",
            "=.tag=listen-generated",
        ]
    ) + client.encode_sentence(
        [
            "/cancel",
            "=tag=listen-generated",
            "=.tag=listen-generated-cancel",
        ]
    )


def test_listen_raises_when_cancel_returns_fatal(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!re", "=.tag=listen-1", "=name=ether1"]))
    fake_socket.response_bytes.extend(client.encode_sentence(["!fatal", "=.tag=listen-1-cancel", "=message=connection closing"]))
    fake_socket.response_bytes.extend(client.encode_sentence(["!done", "=.tag=listen-1"]))
    client._socket = fake_socket

    with pytest.raises(RouterOSFatalError, match="connection closing"):
        client.listen("/interface", tag="listen-1", max_events=1)


def test_cancel_builds_cancel_sentence(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!done", "=ret=ok"]))
    client._socket = fake_socket

    result = client.cancel("listen-1")

    assert result == {"ret": "ok"}
    assert bytes(fake_socket.sent) == client.encode_sentence(
        [
            "/cancel",
            "=tag=listen-1",
        ]
    )


def test_clone_copies_connection_settings(client: RouterOSClient) -> None:
    cloned = client.clone()

    assert cloned is not client
    assert cloned.host == client.host
    assert cloned.username == client.username
    assert cloned.password == client.password
    assert cloned.port == client.port
    assert cloned.use_ssl == client.use_ssl
    assert cloned.tls_verify == client.tls_verify
    assert cloned.timeout == client.timeout


def test_isolated_opens_and_closes_cloned_client(client: RouterOSClient) -> None:
    cloned = Mock(spec=RouterOSClient)
    client.clone = Mock(return_value=cloned)

    with client.isolated() as isolated_client:
        assert isolated_client is cloned

    client.clone.assert_called_once_with()
    cloned.open.assert_called_once_with()
    cloned.close.assert_called_once_with()


def test_read_word_falls_back_to_latin1_for_non_utf8_router_data(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(b"\x01\xf3")
    client._socket = fake_socket

    assert client.read_word() == "ó"


def test_mutation_trap_raises_clear_routeros_error(client: RouterOSClient, fake_socket) -> None:
    fake_socket.response_bytes.extend(client.encode_sentence(["!trap", "=category=1", "=message=failure"]))
    fake_socket.response_bytes.extend(client.encode_sentence(["!done"]))
    client._socket = fake_socket

    with pytest.raises(RouterOSError, match=r"RouterOS command failed \(1\): failure"):
        client.remove("/ip/address", "*3")


@pytest.mark.parametrize("item_id", ["", "   "])
def test_set_requires_non_empty_item_id(client: RouterOSClient, item_id: str) -> None:
    with pytest.raises(ValueError, match="item_id is required"):
        client.set("/ip/address", item_id, attrs={"disabled": True})
