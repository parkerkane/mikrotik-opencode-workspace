from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mikrotik_mcp.client import RouterOSClient


class FakeSocket:
    def __init__(self, response_bytes: bytes = b"") -> None:
        self.response_bytes = bytearray(response_bytes)
        self.sent = bytearray()
        self.closed = False

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)

    def recv(self, size: int) -> bytes:
        if not self.response_bytes:
            return b""
        chunk = self.response_bytes[:size]
        del self.response_bytes[:size]
        return bytes(chunk)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def client() -> RouterOSClient:
    return RouterOSClient("router.test", "admin", "secret", use_ssl=False)


@pytest.fixture
def fake_socket() -> FakeSocket:
    return FakeSocket()
