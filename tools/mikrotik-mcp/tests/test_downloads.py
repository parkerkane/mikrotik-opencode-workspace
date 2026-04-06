from __future__ import annotations

from pathlib import Path

import pytest

from mikrotik_mcp.downloads import FTPFileDownloader, RouterFileDownloadError, load_file_transfer_settings


def test_load_file_transfer_settings_uses_ftp_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIKROTIK_USER", "api-user")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "api-pass")
    monkeypatch.setenv("MIKROTIK_TLS_VERIFY", "false")
    monkeypatch.setenv("MIKROTIK_FTP_HOST", "files.router.test")
    monkeypatch.setenv("MIKROTIK_FTP_USER", "ftp-user")
    monkeypatch.setenv("MIKROTIK_FTP_PASSWORD", "ftp-pass")
    monkeypatch.setenv("MIKROTIK_FTP_PORT", "2121")
    monkeypatch.setenv("MIKROTIK_FTP_TLS", "false")
    monkeypatch.setenv("MIKROTIK_FTP_TIMEOUT", "12.5")

    settings = load_file_transfer_settings("router.test")

    assert settings.host == "files.router.test"
    assert settings.username == "ftp-user"
    assert settings.password == "ftp-pass"
    assert settings.port == 2121
    assert settings.use_tls is False
    assert settings.tls_verify is False
    assert settings.timeout == 12.5


def test_load_file_transfer_settings_falls_back_to_api_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "secret")
    monkeypatch.delenv("MIKROTIK_FTP_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_FTP_PASSWORD", raising=False)
    monkeypatch.delenv("MIKROTIK_FTP_HOST", raising=False)
    monkeypatch.delenv("MIKROTIK_FTP_PORT", raising=False)
    monkeypatch.delenv("MIKROTIK_FTP_TLS", raising=False)
    monkeypatch.delenv("MIKROTIK_FTP_TLS_VERIFY", raising=False)
    monkeypatch.setenv("MIKROTIK_TLS_VERIFY", "true")

    settings = load_file_transfer_settings("router.test")

    assert settings.host == "router.test"
    assert settings.username == "admin"
    assert settings.password == "secret"
    assert settings.port == 21
    assert settings.use_tls is True
    assert settings.tls_verify is True


def test_load_file_transfer_settings_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIKROTIK_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_PASSWORD", raising=False)
    monkeypatch.delenv("MIKROTIK_FTP_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_FTP_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="must be set before downloading files"):
        load_file_transfer_settings("router.test")


class FakeFTPSession:
    def __init__(self, payload: bytes = b"backup-data", *, fail_on_retr: bool = False) -> None:
        self.payload = payload
        self.fail_on_retr = fail_on_retr
        self.connected_to: tuple[str, int] | None = None
        self.logged_in_as: tuple[str, str] | None = None
        self.protected = False
        self.quit_called = False
        self.close_called = False

    def connect(self, host: str, port: int) -> None:
        self.connected_to = (host, port)

    def login(self, username: str, password: str) -> None:
        self.logged_in_as = (username, password)

    def prot_p(self) -> None:
        self.protected = True

    def retrbinary(self, command: str, callback) -> None:
        if self.fail_on_retr:
            raise OSError("read failed")
        assert command == "RETR backups/router.backup"
        callback(self.payload)

    def quit(self) -> None:
        self.quit_called = True

    def close(self) -> None:
        self.close_called = True


def test_ftp_file_downloader_writes_downloaded_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session = FakeFTPSession()
    monkeypatch.setattr("mikrotik_mcp.downloads.FTP_TLS", lambda **_: session)

    settings = load_file_transfer_settings_for_test()
    downloader = FTPFileDownloader(settings)
    destination = tmp_path / "artifacts" / "router.backup"

    downloader.download_file("backups/router.backup", destination)

    assert destination.read_bytes() == b"backup-data"
    assert session.connected_to == ("router.test", 21)
    assert session.logged_in_as == ("admin", "secret")
    assert session.protected is True
    assert session.quit_called is True


def test_ftp_file_downloader_wraps_local_write_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session = FakeFTPSession(fail_on_retr=True)
    monkeypatch.setattr("mikrotik_mcp.downloads.FTP_TLS", lambda **_: session)

    downloader = FTPFileDownloader(load_file_transfer_settings_for_test())

    with pytest.raises(RouterFileDownloadError, match="Failed to write local file|Failed to download router file"):
        downloader.download_file("backups/router.backup", tmp_path / "router.backup")


def load_file_transfer_settings_for_test():
    class Settings:
        host = "router.test"
        username = "admin"
        password = "secret"
        port = 21
        use_tls = True
        tls_verify = False
        timeout = 5.0

    return Settings()
