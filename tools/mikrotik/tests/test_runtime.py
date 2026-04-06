from __future__ import annotations

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
