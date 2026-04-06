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

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import socket
import ssl
from typing import Any
from uuid import uuid4


class RouterOSError(RuntimeError):
    pass


class RouterOSTransportError(RouterOSError):
    pass


class RouterOSAuthError(RouterOSError):
    pass


class RouterOSFatalError(RouterOSError):
    pass


@dataclass(slots=True)
class ReplyBundle:
    records: list[dict[str, str]] = field(default_factory=list)
    done: dict[str, str] = field(default_factory=dict)
    traps: list[dict[str, str]] = field(default_factory=list)
    fatal: dict[str, str] | None = None
    empty: bool = False
    tag: str | None = None


@dataclass(slots=True)
class ListenResult:
    tag: str
    records: list[dict[str, str]] = field(default_factory=list)
    done: dict[str, str] = field(default_factory=dict)
    traps: list[dict[str, str]] = field(default_factory=list)
    fatal: dict[str, str] | None = None
    empty: bool = False
    cancelled: bool = False
    limit_reached: bool = False
    cancel_done: dict[str, str] = field(default_factory=dict)
    cancel_fatal: dict[str, str] | None = None


def encode_length(length: int) -> bytes:
    if length < 0:
        raise ValueError("Word length must be non-negative")
    if length < 0x80:
        return bytes([length])
    if length < 0x4000:
        length |= 0x8000
        return length.to_bytes(2, "big")
    if length < 0x200000:
        length |= 0xC00000
        return length.to_bytes(3, "big")
    if length < 0x10000000:
        length |= 0xE0000000
        return length.to_bytes(4, "big")
    if length < 0x100000000:
        return b"\xF0" + length.to_bytes(4, "big")
    raise ValueError("Word length exceeds RouterOS API limit")


def decode_length(reader: Any) -> int:
    first = reader.read(1)
    if len(first) != 1:
        raise EOFError("Unexpected EOF while reading RouterOS word length")

    value = first[0]
    if (value & 0x80) == 0x00:
        return value
    if (value & 0xC0) == 0x80:
        rest = reader.read(1)
        if len(rest) != 1:
            raise EOFError("Unexpected EOF while reading RouterOS word length")
        return int.from_bytes(bytes([value]) + rest, "big") & ~0x8000
    if (value & 0xE0) == 0xC0:
        rest = reader.read(2)
        if len(rest) != 2:
            raise EOFError("Unexpected EOF while reading RouterOS word length")
        return int.from_bytes(bytes([value]) + rest, "big") & ~0xC00000
    if (value & 0xF0) == 0xE0:
        rest = reader.read(3)
        if len(rest) != 3:
            raise EOFError("Unexpected EOF while reading RouterOS word length")
        return int.from_bytes(bytes([value]) + rest, "big") & ~0xE0000000
    if value == 0xF0:
        rest = reader.read(4)
        if len(rest) != 4:
            raise EOFError("Unexpected EOF while reading RouterOS word length")
        return int.from_bytes(rest, "big")
    raise ValueError(f"Unsupported RouterOS length prefix: 0x{value:02x}")


def parse_reply_sentences(sentences: list[list[str]]) -> ReplyBundle:
    bundle = ReplyBundle()

    for sentence in sentences:
        if not sentence:
            continue

        reply_type, attrs = parse_reply_sentence(sentence)
        if bundle.tag is None:
            bundle.tag = attrs.get(".tag")

        if reply_type == "!re":
            bundle.records.append(attrs)
        elif reply_type == "!done":
            bundle.done = attrs
        elif reply_type == "!trap":
            bundle.traps.append(attrs)
        elif reply_type == "!fatal":
            bundle.fatal = attrs
        elif reply_type == "!empty":
            bundle.empty = True

    return bundle


def parse_reply_sentence(sentence: list[str]) -> tuple[str, dict[str, str]]:
    if not sentence:
        raise ValueError("sentence must not be empty")

    reply_type, *words = sentence
    attrs: dict[str, str] = {}
    for word in words:
        if not word:
            continue
        if word.startswith(".") and "=" in word:
            key, _, value = word.partition("=")
            attrs[key] = value
            continue
        if word.startswith("="):
            key, _, value = word[1:].partition("=")
            attrs[key] = value
            continue
        attrs[word] = ""
    return reply_type, attrs


class RouterOSClient:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int | None = None,
        use_ssl: bool = False,
        tls_verify: bool = True,
        tls_ca_files: tuple[str, ...] = (),
        timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.port = port or (8729 if use_ssl else 8728)
        self.use_ssl = use_ssl
        self.tls_verify = tls_verify
        self.tls_ca_files = tls_ca_files
        self.timeout = timeout
        self._socket: socket.socket | ssl.SSLSocket | None = None

    def connect(self) -> None:
        try:
            raw_socket = socket.create_connection((self.host, self.port), self.timeout)
            raw_socket.settimeout(self.timeout)
            if self.use_ssl:
                context = ssl.create_default_context()
                if self.tls_verify:
                    for cert_file in self.tls_ca_files:
                        context.load_verify_locations(cafile=str(Path(cert_file)))
                else:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                self._socket = context.wrap_socket(raw_socket, server_hostname=self.host if self.tls_verify else None)
            else:
                self._socket = raw_socket
        except ssl.SSLError as exc:
            raise RouterOSTransportError(
                f"TLS connection to {self.host}:{self.port} failed. Place trusted CA certs in certs/ or set MIKROTIK_TLS_VERIFY=false for self-signed lab certs. {exc}"
            ) from exc
        except OSError as exc:
            raise RouterOSTransportError(f"Failed to connect to {self.host}:{self.port}: {exc}") from exc

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def open(self) -> None:
        self.connect()
        self.login()

    def clone(self) -> RouterOSClient:
        return RouterOSClient(
            self.host,
            self.username,
            self.password,
            port=self.port,
            use_ssl=self.use_ssl,
            tls_verify=self.tls_verify,
            tls_ca_files=self.tls_ca_files,
            timeout=self.timeout,
        )

    @contextmanager
    def isolated(self) -> Iterator[RouterOSClient]:
        isolated_client = self.clone()
        isolated_client.open()
        try:
            yield isolated_client
        finally:
            isolated_client.close()

    def login(self) -> None:
        reply = self.command("/login", attrs={"name": self.username, "password": self.password})
        if reply.traps:
            trap = reply.traps[0]
            message = trap.get("message", "Login failed")
            raise RouterOSAuthError(f"RouterOS login failed for user '{self.username}': {message}")
        if reply.fatal:
            raise RouterOSFatalError(reply.fatal.get("message", "RouterOS connection ended during login"))

    def tls_session_info(self) -> dict[str, Any] | None:
        if not self.use_ssl or self._socket is None or not hasattr(self._socket, "getpeercert"):
            return None

        certificate = self._socket.getpeercert()
        if not certificate:
            return None

        der_certificate = self._socket.getpeercert(binary_form=True)
        cipher = self._socket.cipher()
        return {
            "subject": _distinguished_name(certificate.get("subject")),
            "issuer": _distinguished_name(certificate.get("issuer")),
            "serial_number": certificate.get("serialNumber"),
            "not_before": certificate.get("notBefore"),
            "not_after": certificate.get("notAfter"),
            "subject_alt_names": [value for kind, value in certificate.get("subjectAltName", ()) if kind == "DNS"],
            "sha256_fingerprint": hashlib.sha256(der_certificate).hexdigest().upper() if der_certificate else None,
            "tls_version": self._socket.version() if hasattr(self._socket, "version") else None,
            "cipher": cipher[0] if cipher else None,
            "cipher_bits": cipher[2] if cipher and len(cipher) > 2 else None,
            "hostname_verified": self.tls_verify,
        }

    def print(
        self,
        menu: str,
        *,
        proplist: list[str] | None = None,
        queries: list[str] | None = None,
        attrs: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        normalized_menu = _normalize_menu(menu)
        sentence = [f"{normalized_menu}/print"]
        if proplist:
            sentence.append(f"=.proplist={','.join(proplist)}")
        for key, value in _normalize_attrs(attrs).items():
            sentence.append(f"={key}={value}")
        for query in _normalize_queries(queries):
            sentence.append(query)

        reply = self.execute(sentence)
        self._raise_for_errors(reply)
        return reply.records

    def add(self, menu: str, *, attrs: dict[str, Any] | None = None) -> dict[str, str] | dict[str, bool]:
        reply = self.execute(self._build_menu_sentence(menu, "add", attrs=attrs))
        return self._normalize_mutation_result(reply)

    def set(self, menu: str, item_id: str, *, attrs: dict[str, Any] | None = None) -> dict[str, str] | dict[str, bool]:
        reply = self.execute(self._build_menu_sentence(menu, "set", item_id=item_id, attrs=attrs))
        return self._normalize_mutation_result(reply)

    def remove(self, menu: str, item_id: str) -> dict[str, str] | dict[str, bool]:
        reply = self.execute(self._build_menu_sentence(menu, "remove", item_id=item_id))
        return self._normalize_mutation_result(reply)

    def run(
        self,
        path: str,
        *,
        attrs: dict[str, Any] | None = None,
        queries: list[str] | None = None,
        tag: str | None = None,
    ) -> list[dict[str, str]] | dict[str, str] | dict[str, bool]:
        sentence = self._build_command_sentence(path, attrs=attrs, queries=queries, tag=tag)
        reply = self.execute(sentence)
        self._raise_for_errors(reply)
        if reply.records:
            return reply.records
        return self._normalize_mutation_result(reply)

    def listen(
        self,
        menu: str,
        *,
        proplist: list[str] | None = None,
        queries: list[str] | None = None,
        attrs: dict[str, Any] | None = None,
        tag: str | None = None,
        max_events: int = 10,
    ) -> ListenResult:
        if max_events < 1:
            raise ValueError("max_events must be at least 1")

        listen_tag = _normalize_tag(tag) if tag is not None else self._generate_tag("listen")
        cancel_tag = self._cancel_tag(listen_tag)
        sentence = [f"{_normalize_menu(menu)}/listen"]
        if proplist:
            sentence.append(f"=.proplist={','.join(proplist)}")
        for key, value in _normalize_attrs(attrs).items():
            sentence.append(f"={key}={value}")
        for query in _normalize_queries(queries):
            sentence.append(query)
        sentence.append(f".tag={listen_tag}")

        result = ListenResult(tag=listen_tag)
        self.write_sentence(sentence)

        cancel_sent = False
        listen_done = False
        cancel_done = False
        while True:
            try:
                reply_type, reply_attrs = parse_reply_sentence(self.read_sentence())
            except RouterOSTransportError as exc:
                if "timed out" not in str(exc).lower() or cancel_sent:
                    raise
                result.cancelled = True
                self.write_sentence(self._build_cancel_sentence(listen_tag, cancel_tag=cancel_tag))
                cancel_sent = True
                continue
            reply_tag = reply_attrs.get(".tag")

            if reply_tag == listen_tag or (reply_tag is None and not cancel_sent and reply_type in {"!trap", "!fatal", "!done", "!empty"}):
                if reply_type == "!re":
                    result.records.append(reply_attrs)
                    if len(result.records) >= max_events and not cancel_sent:
                        result.limit_reached = True
                        result.cancelled = True
                        self.write_sentence(self._build_cancel_sentence(listen_tag, cancel_tag=cancel_tag))
                        cancel_sent = True
                elif reply_type == "!trap":
                    if cancel_sent and reply_attrs.get("message") == "interrupted":
                        result.cancelled = True
                    else:
                        result.traps.append(reply_attrs)
                elif reply_type == "!done":
                    result.done = reply_attrs
                    listen_done = True
                elif reply_type == "!fatal":
                    result.fatal = reply_attrs
                    listen_done = True
                elif reply_type == "!empty":
                    result.empty = True

            if reply_tag == cancel_tag or (cancel_sent and reply_tag is None and reply_type in {"!done", "!fatal"}):
                if reply_type == "!done":
                    result.cancel_done = reply_attrs
                    cancel_done = True
                elif reply_type == "!fatal":
                    result.cancel_fatal = reply_attrs
                    cancel_done = True

            if result.cancel_fatal or (listen_done and (not cancel_sent or cancel_done)):
                break

        if result.cancel_fatal:
            raise RouterOSFatalError(result.cancel_fatal.get("message", "RouterOS cancel command ended unexpectedly"))
        if result.fatal:
            raise RouterOSFatalError(result.fatal.get("message", "RouterOS connection ended unexpectedly"))
        return result

    def cancel(self, tag: str) -> dict[str, str] | dict[str, bool]:
        reply = self.execute(self._build_cancel_sentence(tag))
        return self._normalize_mutation_result(reply)

    def command(self, path: str, attrs: dict[str, Any] | None = None) -> ReplyBundle:
        sentence = self._build_command_sentence(path, attrs=attrs)

        reply = self.execute(sentence)
        if reply.fatal:
            raise RouterOSFatalError(reply.fatal.get("message", "RouterOS connection ended unexpectedly"))
        return reply

    def _build_command_sentence(
        self,
        path: str,
        *,
        attrs: dict[str, Any] | None = None,
        queries: list[str] | None = None,
        tag: str | None = None,
    ) -> list[str]:
        sentence = [_normalize_command_path(path)]
        for key, value in _normalize_attrs(attrs).items():
            sentence.append(f"={key}={value}")
        for query in _normalize_queries(queries):
            sentence.append(query)
        if tag is not None:
            sentence.append(f".tag={_normalize_tag(tag)}")
        return sentence

    def execute(self, words: list[str]) -> ReplyBundle:
        if self._socket is None:
            self.open()

        self.write_sentence(words)
        sentences: list[list[str]] = []
        while True:
            sentence = self.read_sentence()
            sentences.append(sentence)
            if sentence and sentence[0] in {"!done", "!fatal"}:
                break

        return parse_reply_sentences(sentences)

    def write_sentence(self, words: list[str]) -> None:
        self._sendall(self.encode_sentence(words))

    def read_sentence(self) -> list[str]:
        words: list[str] = []
        while True:
            word = self.read_word()
            if word == "":
                return words
            words.append(word)

    def read_word(self) -> str:
        if self._socket is None:
            raise RouterOSTransportError("RouterOS socket is not connected")
        length = decode_length(self)
        if length == 0:
            return ""
        data = self._read_exact(length)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            # RouterOS file metadata can contain bytes that are not valid UTF-8.
            return data.decode("latin-1")

    def read(self, size: int) -> bytes:
        return self._read_exact(size)

    def encode_sentence(self, words: list[str]) -> bytes:
        encoded = bytearray()
        for word in words:
            data = word.encode("utf-8")
            encoded.extend(encode_length(len(data)))
            encoded.extend(data)
        encoded.append(0)
        return bytes(encoded)

    def _sendall(self, data: bytes) -> None:
        if self._socket is None:
            raise RouterOSTransportError("RouterOS socket is not connected")
        try:
            self._socket.sendall(data)
        except OSError as exc:
            raise RouterOSTransportError(f"Failed to send RouterOS API sentence: {exc}") from exc

    def _read_exact(self, size: int) -> bytes:
        if self._socket is None:
            raise RouterOSTransportError("RouterOS socket is not connected")

        chunks = bytearray()
        while len(chunks) < size:
            try:
                chunk = self._socket.recv(size - len(chunks))
            except TimeoutError as exc:
                raise RouterOSTransportError("RouterOS API read timed out") from exc
            except OSError as exc:
                raise RouterOSTransportError(f"RouterOS API read failed: {exc}") from exc
            if not chunk:
                raise RouterOSTransportError("RouterOS API connection closed unexpectedly")
            chunks.extend(chunk)
        return bytes(chunks)

    @staticmethod
    def _raise_for_errors(reply: ReplyBundle) -> None:
        if reply.traps:
            trap = reply.traps[0]
            message = trap.get("message", "RouterOS command failed")
            category = trap.get("category")
            if category:
                raise RouterOSError(f"RouterOS command failed ({category}): {message}")
            raise RouterOSError(f"RouterOS command failed: {message}")
        if reply.fatal:
            raise RouterOSFatalError(reply.fatal.get("message", "RouterOS connection ended unexpectedly"))

    def _build_menu_sentence(
        self,
        menu: str,
        action: str,
        *,
        item_id: str | None = None,
        attrs: dict[str, Any] | None = None,
    ) -> list[str]:
        sentence = [f"{_normalize_menu(menu)}/{action}"]
        if item_id is not None:
            sentence.append(f"=.id={_normalize_item_id(item_id)}")
        for key, value in _normalize_attrs(attrs).items():
            sentence.append(f"={key}={value}")
        return sentence

    def _build_cancel_sentence(self, tag: str, *, cancel_tag: str | None = None) -> list[str]:
        _ = cancel_tag
        return ["/cancel", f"=tag={_normalize_tag(tag)}"]

    def _cancel_tag(self, tag: str) -> str:
        return f"{tag}-cancel"

    def _generate_tag(self, prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:12]}"

    @classmethod
    def _normalize_mutation_result(cls, reply: ReplyBundle) -> dict[str, str] | dict[str, bool]:
        cls._raise_for_errors(reply)
        if reply.done:
            return reply.done
        if reply.empty:
            return {"success": True, "empty": True}
        return {"success": True}


def _distinguished_name(parts: Any) -> str | None:
    if not parts:
        return None

    attributes: list[str] = []
    for entry in parts:
        for key, value in entry:
            attributes.append(f"{key}={value}")
    return ", ".join(attributes) if attributes else None


def _normalize_menu(menu: str) -> str:
    if not menu or not menu.strip():
        raise ValueError("menu is required")
    return "/" + menu.strip().strip("/")


def _normalize_item_id(item_id: str) -> str:
    if not item_id or not item_id.strip():
        raise ValueError("item_id is required")
    return item_id.strip()


def _normalize_command_path(path: str) -> str:
    if not path or not path.strip():
        raise ValueError("command path is required")
    return "/" + path.strip().strip("/")


def _normalize_tag(tag: str) -> str:
    value = tag.strip()
    if not value:
        raise ValueError("tag is required")
    if any(char.isspace() for char in value):
        raise ValueError("tag must not contain whitespace")
    return value


def _normalize_queries(queries: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for query in queries or []:
        value = query.strip()
        if not value:
            raise ValueError("query entries must not be empty")
        if any(char.isspace() for char in value):
            raise ValueError(f"query '{query}' must not contain whitespace")
        if not value.startswith("?"):
            value = f"?{value}"
        normalized.append(value)
    return normalized


def _normalize_attrs(attrs: dict[str, Any] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in (attrs or {}).items():
        if value is None:
            continue
        normalized[str(key)] = _stringify(value)
    return normalized


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
