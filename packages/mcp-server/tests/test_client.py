from __future__ import annotations

from io import BytesIO

import pytest

from mikrotik_mcp.client import RouterOSClient, encode_length, decode_length, parse_reply_sentences


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
