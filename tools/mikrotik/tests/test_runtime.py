from __future__ import annotations

import pytest

from mikrotik_mcp import runtime


def test_load_tls_ca_files_returns_sorted_active_files(tmp_path, monkeypatch) -> None:
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    (certs_dir / "zeta.pem").write_text("zeta", encoding="utf-8")
    (certs_dir / "alpha.crt").write_text("alpha", encoding="utf-8")
    (certs_dir / "README.md").write_text("docs", encoding="utf-8")
    (certs_dir / "ignored.pem.disabled").write_text("ignore", encoding="utf-8")

    monkeypatch.setattr(runtime, "workspace_root", lambda: tmp_path)

    assert runtime.load_tls_ca_files() == (
        str(certs_dir / "alpha.crt"),
        str(certs_dir / "zeta.pem"),
    )


def test_load_tls_ca_files_returns_empty_tuple_when_directory_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runtime, "workspace_root", lambda: tmp_path)

    assert runtime.load_tls_ca_files() == ()


def test_load_settings_passes_discovered_tls_ca_files(monkeypatch) -> None:
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "secret")
    monkeypatch.setenv("MIKROTIK_API_SSL", "true")
    monkeypatch.setenv("MIKROTIK_TLS_VERIFY", "true")
    monkeypatch.delenv("MIKROTIK_API_PORT", raising=False)
    monkeypatch.setattr(runtime, "load_dotenv", lambda path: None)
    monkeypatch.setattr(runtime, "load_tls_ca_files", lambda: ("/work/certs/router-ca.pem",))

    client = runtime.load_settings("router.test")

    assert client.host == "router.test"
    assert client.port == 8729
    assert client.use_ssl is True
    assert client.tls_verify is True
    assert client.tls_ca_files == ("/work/certs/router-ca.pem",)


def test_load_settings_rotates_password_when_passwordless_enabled(monkeypatch) -> None:
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.delenv("MIKROTIK_PASSWORD", raising=False)
    monkeypatch.setenv("MIKROTIK_API_PASSWORDLESS_ENABLED", "true")
    monkeypatch.setattr(runtime, "load_dotenv", lambda path: None)
    monkeypatch.setattr(runtime, "load_tls_ca_files", lambda: ())
    monkeypatch.setattr(runtime, "rotate_startup_api_password", lambda host, username: "rotated-secret")

    client = runtime.load_settings("router.test")

    assert client.username == "admin"
    assert client.password == "rotated-secret"


def test_load_settings_requires_password_when_passwordless_disabled(monkeypatch) -> None:
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.delenv("MIKROTIK_PASSWORD", raising=False)
    monkeypatch.delenv("MIKROTIK_API_PASSWORDLESS_ENABLED", raising=False)
    monkeypatch.setattr(runtime, "load_dotenv", lambda path: None)

    with pytest.raises(RuntimeError, match="MIKROTIK_USER and MIKROTIK_PASSWORD"):
        runtime.load_settings("router.test")


def test_rotate_startup_api_password_uses_requested_length(monkeypatch) -> None:
    seen: dict[str, str] = {}
    monkeypatch.setenv("MIKROTIK_API_PASSWORDLESS_LENGTH", "40")
    monkeypatch.setattr(runtime, "generate_api_password", lambda length: "x" * length)
    monkeypatch.setattr(
        runtime,
        "rotate_routeros_user_password",
        lambda **kwargs: seen.update(kwargs),
    )

    password = runtime.rotate_startup_api_password("router.test", username="admin")

    assert password == "x" * 40
    assert seen == {"host": "router.test", "username": "admin", "new_password": "x" * 40}


def test_rotate_startup_api_password_rejects_invalid_length(monkeypatch) -> None:
    monkeypatch.setenv("MIKROTIK_API_PASSWORDLESS_LENGTH", "0")

    with pytest.raises(RuntimeError, match="at least 1"):
        runtime.rotate_startup_api_password("router.test", username="admin")
