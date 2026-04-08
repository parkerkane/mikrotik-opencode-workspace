from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import paramiko
import pytest

from mikrotik_mcp.downloads import (
    PermissiveMissingHostKeyPolicy,
    SCPFileDownloader,
    check_routeros_password_rotation_ready,
    RouterFileDownloadError,
    RouterSSHCommandError,
    load_file_transfer_settings,
    load_password_rotation_settings,
    open_ssh_client,
    rotate_routeros_user_password,
)


FAKE_HOST_KEY_BYTES = b"router-host-key"


def fake_host_key_fingerprint() -> str:
    digest = hashlib.sha256(FAKE_HOST_KEY_BYTES).digest()
    return f"SHA256:{base64.b64encode(digest).decode('ascii').rstrip('=')}"


def test_load_file_transfer_settings_uses_scp_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setenv("MIKROTIK_USER", "api-user")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "api-pass")
    monkeypatch.setenv("MIKROTIK_SCP_HOST", "files.router.test")
    monkeypatch.setenv("MIKROTIK_SCP_USER", "scp-user")
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "scp-pass")
    monkeypatch.delenv("MIKROTIK_SCP_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())
    monkeypatch.setenv("MIKROTIK_SCP_PORT", "2222")
    monkeypatch.setenv("MIKROTIK_SCP_TIMEOUT", "12.5")

    settings = load_file_transfer_settings("router.test")

    assert settings.host == "files.router.test"
    assert settings.username == "scp-user"
    assert settings.password == "scp-pass"
    assert settings.private_key is None
    assert settings.ssh_host_fingerprint_sha256 == fake_host_key_fingerprint()
    assert settings.port == 2222
    assert settings.timeout == 12.5


def test_load_file_transfer_settings_falls_back_to_api_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "secret")
    monkeypatch.delenv("MIKROTIK_SCP_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PASSWORD", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_HOST", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PORT", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())

    settings = load_file_transfer_settings("router.test")

    assert settings.host == "router.test"
    assert settings.username == "admin"
    assert settings.password == "secret"
    assert settings.private_key is None
    assert settings.port == 22


def test_load_file_transfer_settings_uses_explicit_private_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    private_key = tmp_path / "router-key"
    private_key.write_text("private-key", encoding="utf-8")
    monkeypatch.setenv("MIKROTIK_SCP_USER", "mcprw")
    monkeypatch.setenv("MIKROTIK_SCP_PRIVATE_KEY", str(private_key))
    monkeypatch.setenv("MIKROTIK_SCP_KEY_PASSPHRASE", "phrase")
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "ignored-pass")
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())

    settings = load_file_transfer_settings("router.test")

    assert settings.username == "mcprw"
    assert settings.private_key == str(private_key)
    assert settings.key_passphrase == "phrase"
    assert settings.password is None


def test_load_file_transfer_settings_does_not_use_default_router_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    (certs_dir / "router-key").write_text("private-key", encoding="utf-8")
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setenv("MIKROTIK_SCP_USER", "mcprw")
    monkeypatch.delenv("MIKROTIK_SCP_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "scp-pass")
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())

    settings = load_file_transfer_settings("router.test")

    assert settings.username == "mcprw"
    assert settings.private_key is None
    assert settings.password == "scp-pass"


def test_load_file_transfer_settings_requires_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.delenv("MIKROTIK_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_PASSWORD", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_SCP_PASSWORD", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())
    monkeypatch.setenv("MIKROTIK_SCP_PRIVATE_KEY", "/definitely/missing/key")

    with pytest.raises(RuntimeError, match="SCP private key file"):
        load_file_transfer_settings("router.test")


def test_load_file_transfer_settings_requires_auth_when_no_key_or_password(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.delenv("MIKROTIK_USER", raising=False)
    monkeypatch.delenv("MIKROTIK_PASSWORD", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_USER", "mcprw")
    monkeypatch.delenv("MIKROTIK_SCP_PASSWORD", raising=False)
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())
    monkeypatch.setenv("MIKROTIK_SCP_PRIVATE_KEY", str(tmp_path / "missing-key"))

    with pytest.raises(RuntimeError, match="SCP private key file"):
        load_file_transfer_settings("router.test")


def test_load_file_transfer_settings_requires_host_key_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "secret")
    monkeypatch.delenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", raising=False)

    settings = load_file_transfer_settings("router.test")

    assert settings.ssh_host_fingerprint_sha256 is None


def test_load_file_transfer_settings_rejects_invalid_host_key_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.setenv("MIKROTIK_PASSWORD", "secret")
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", "not-a-fingerprint")

    with pytest.raises(ValueError, match="OpenSSH-style SHA256 fingerprint"):
        load_file_transfer_settings("router.test")


class FakeDirEntry:
    def __init__(self, filename: str) -> None:
        self.filename = filename


class FakeRemoteFile:
    def __init__(self, payload: bytes = b"backup-data", *, fail_on_read: bool = False) -> None:
        self.payload = payload
        self.fail_on_read = fail_on_read

    def read(self) -> bytes:
        if self.fail_on_read:
            raise OSError("read failed")
        return self.payload

    def close(self) -> None:
        return None


class FakeSFTPClient:
    def __init__(self, payload: bytes = b"backup-data", *, fail_on_read: bool = False, fail_on_listdir: bool = False) -> None:
        self.payload = payload
        self.fail_on_read = fail_on_read
        self.fail_on_listdir = fail_on_listdir
        self.closed = False

    def normalize(self, path: str) -> str:
        assert path == "."
        return "/"

    def listdir_attr(self, path: str) -> list[FakeDirEntry]:
        assert path == "/"
        if self.fail_on_listdir:
            raise OSError("listing failed")
        return [FakeDirEntry("backups"), FakeDirEntry("flash"), FakeDirEntry("skins")]

    def file(self, path: str, mode: str = "rb") -> FakeRemoteFile:
        assert path == "backups/router.backup"
        assert mode == "rb"
        return FakeRemoteFile(self.payload, fail_on_read=self.fail_on_read)

    def close(self) -> None:
        self.closed = True


class FakeSSHClient:
    def __init__(
        self,
        *,
        fail_on_connect: bool = False,
        fail_on_exec: bool = False,
        exec_stdout: bytes = b"",
        exec_stderr: bytes = b"",
        exec_exit_status: int = 0,
        sftp_client: FakeSFTPClient | None = None,
        server_key_bytes: bytes = FAKE_HOST_KEY_BYTES,
    ) -> None:
        self.connected_to: tuple[str, int] | None = None
        self.connect_kwargs: dict[str, object] | None = None
        self.close_called = False
        self.policy = None
        self.fail_on_connect = fail_on_connect
        self.fail_on_exec = fail_on_exec
        self.exec_stdout = exec_stdout
        self.exec_stderr = exec_stderr
        self.exec_exit_status = exec_exit_status
        self.commands: list[tuple[str, float | None]] = []
        self.sftp_client = sftp_client or FakeSFTPClient()
        self.server_key = FakeHostKey(server_key_bytes)

    def set_missing_host_key_policy(self, policy) -> None:
        self.policy = policy

    def connect(self, **kwargs) -> None:
        if self.fail_on_connect:
            raise OSError("connect failed")
        if self.policy is not None:
            self.policy.missing_host_key(self, kwargs["hostname"], self.server_key)
        self.connected_to = (kwargs["hostname"], kwargs["port"])
        self.connect_kwargs = kwargs

    def open_sftp(self) -> FakeSFTPClient:
        return self.sftp_client

    def exec_command(self, command: str, timeout: float | None = None):
        if self.fail_on_exec:
            raise OSError("exec failed")
        self.commands.append((command, timeout))
        return (
            None,
            FakeExecStream(self.exec_stdout, exit_status=self.exec_exit_status),
            FakeExecStream(self.exec_stderr, exit_status=self.exec_exit_status),
        )

    def close(self) -> None:
        self.close_called = True


class FakeExecChannel:
    def __init__(self, exit_status: int) -> None:
        self.exit_status = exit_status

    def recv_exit_status(self) -> int:
        return self.exit_status


class FakeExecStream:
    def __init__(self, payload: bytes, *, exit_status: int) -> None:
        self.payload = payload
        self.channel = FakeExecChannel(exit_status)

    def read(self) -> bytes:
        return self.payload


class FakeHostKey:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def asbytes(self) -> bytes:
        return self.payload


def test_scp_file_downloader_writes_downloaded_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    settings = load_file_transfer_settings_for_test()
    downloader = SCPFileDownloader(settings)
    destination = tmp_path / "artifacts" / "router.backup"

    downloader.download_file("backups/router.backup", destination)

    assert destination.read_bytes() == b"backup-data"
    assert ssh_client.connected_to == ("router.test", 22)
    assert ssh_client.connect_kwargs == {
        "hostname": "router.test",
        "port": 22,
        "username": "admin",
        "password": "secret",
        "timeout": 5.0,
    }
    assert ssh_client.close_called is True


def test_scp_file_downloader_check_connection_logs_in_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    downloader = SCPFileDownloader(load_file_transfer_settings_for_test())

    result = downloader.check_connection()

    assert ssh_client.connected_to == ("router.test", 22)
    assert ssh_client.connect_kwargs == {
        "hostname": "router.test",
        "port": 22,
        "username": "admin",
        "password": "secret",
        "timeout": 5.0,
    }
    assert ssh_client.close_called is True
    assert result == {
        "working_directory": "/",
        "listing_count": 3,
        "listing_sample": ["backups", "flash", "skins"],
        "operation": "normalize+listdir_attr",
    }


def test_scp_file_downloader_wraps_local_write_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    downloader = SCPFileDownloader(load_file_transfer_settings_for_test())

    with pytest.raises(RouterFileDownloadError, match="Failed to write local file"):
        downloader.download_file("backups/router.backup", tmp_path)


def test_scp_file_downloader_check_connection_wraps_connect_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mikrotik_mcp.downloads.paramiko.SSHClient",
        lambda: FakeSSHClient(fail_on_connect=True),
    )

    downloader = SCPFileDownloader(load_file_transfer_settings_for_test())

    with pytest.raises(RouterFileDownloadError, match="Failed to connect to SCP service"):
        downloader.check_connection()


def test_scp_file_downloader_check_connection_wraps_directory_probe_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh_client = FakeSSHClient(sftp_client=FakeSFTPClient(fail_on_listdir=True))
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    downloader = SCPFileDownloader(load_file_transfer_settings_for_test())

    with pytest.raises(RouterFileDownloadError, match="directory probe failed"):
        downloader.check_connection()

    assert ssh_client.close_called is True


def test_scp_file_downloader_prefers_private_key(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    downloader = SCPFileDownloader(load_key_transfer_settings_for_test())

    downloader.check_connection()

    assert ssh_client.connect_kwargs == {
        "hostname": "router.test",
        "port": 22,
        "username": "mcprw",
        "key_filename": "/workspace/certs/router-key",
        "passphrase": "phrase",
        "timeout": 5.0,
    }


def test_open_ssh_client_rejects_mismatched_host_key(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh_client = FakeSSHClient(server_key_bytes=b"unexpected-host-key")
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    with pytest.raises(paramiko.SSHException, match="SSH host key fingerprint mismatch"):
        open_ssh_client(load_file_transfer_settings_for_test())


def test_open_ssh_client_allows_missing_host_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)

    settings = load_file_transfer_settings_for_test()
    settings.ssh_host_fingerprint_sha256 = None

    open_ssh_client(settings)

    assert isinstance(ssh_client.policy, PermissiveMissingHostKeyPolicy)


def test_load_password_rotation_settings_requires_private_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setenv("MIKROTIK_USER", "admin")
    monkeypatch.setenv("MIKROTIK_SCP_PASSWORD", "secret")
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())
    monkeypatch.delenv("MIKROTIK_SCP_PRIVATE_KEY", raising=False)

    with pytest.raises(RuntimeError, match="MIKROTIK_SCP_PRIVATE_KEY"):
        load_password_rotation_settings("router.test")


def test_rotate_routeros_user_password_runs_routeros_command_over_ssh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    private_key = tmp_path / "router-key"
    private_key.write_text("private-key", encoding="utf-8")
    ssh_client = FakeSSHClient()
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)
    monkeypatch.setenv("MIKROTIK_SCP_USER", "admin")
    monkeypatch.setenv("MIKROTIK_SCP_PRIVATE_KEY", str(private_key))
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())
    monkeypatch.setenv("MIKROTIK_SCP_TIMEOUT", "9")

    rotate_routeros_user_password(host="router.test", username="admin", new_password="A" * 32)

    assert ssh_client.connect_kwargs == {
        "hostname": "router.test",
        "port": 22,
        "username": "admin",
        "key_filename": str(private_key),
        "timeout": 9.0,
    }
    assert ssh_client.commands == [('/user set [find where name=admin] password=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', 9.0)]
    assert ssh_client.close_called is True


def test_rotate_routeros_user_password_wraps_remote_command_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    private_key = tmp_path / "router-key"
    private_key.write_text("private-key", encoding="utf-8")
    ssh_client = FakeSSHClient(exec_stderr=b"permission denied", exec_exit_status=1)
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)
    monkeypatch.setenv("MIKROTIK_SCP_USER", "admin")
    monkeypatch.setenv("MIKROTIK_SCP_PRIVATE_KEY", str(private_key))
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())

    with pytest.raises(RouterSSHCommandError, match="permission denied"):
        rotate_routeros_user_password(host="router.test", username="admin", new_password="A" * 32)

    assert ssh_client.close_called is True


def test_check_routeros_password_rotation_ready_runs_harmless_user_probe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    private_key = tmp_path / "router-key"
    private_key.write_text("private-key", encoding="utf-8")
    ssh_client = FakeSSHClient(exec_stdout=b"1\n")
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)
    monkeypatch.setenv("MIKROTIK_SCP_USER", "admin")
    monkeypatch.setenv("MIKROTIK_SCP_PRIVATE_KEY", str(private_key))
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())

    result = check_routeros_password_rotation_ready(host="router.test", username="admin")

    assert result == {
        "host": "router.test",
        "port": 22,
        "username": "admin",
        "target_exists": True,
        "command": "/user print count-only where name=admin",
    }
    assert ssh_client.commands == [("/user print count-only where name=admin", 30.0)]
    assert ssh_client.close_called is True


def test_check_routeros_password_rotation_ready_rejects_missing_target_user(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    private_key = tmp_path / "router-key"
    private_key.write_text("private-key", encoding="utf-8")
    ssh_client = FakeSSHClient(exec_stdout=b"0\n")
    monkeypatch.setattr("mikrotik_mcp.downloads.workspace_root", lambda: tmp_path)
    monkeypatch.setattr("mikrotik_mcp.downloads.paramiko.SSHClient", lambda: ssh_client)
    monkeypatch.setenv("MIKROTIK_SCP_USER", "admin")
    monkeypatch.setenv("MIKROTIK_SCP_PRIVATE_KEY", str(private_key))
    monkeypatch.setenv("MIKROTIK_SCP_HOST_FINGERPRINT_SHA256", fake_host_key_fingerprint())

    with pytest.raises(RouterSSHCommandError, match="was not found over SSH"):
        check_routeros_password_rotation_ready(host="router.test", username="admin")


def load_file_transfer_settings_for_test():
    class Settings:
        host = "router.test"
        username = "admin"
        password = "secret"
        private_key = None
        key_passphrase = None
        ssh_host_fingerprint_sha256 = fake_host_key_fingerprint()
        port = 22
        timeout = 5.0

    return Settings()


def load_key_transfer_settings_for_test():
    class Settings:
        host = "router.test"
        username = "mcprw"
        password = "secret"
        private_key = "/workspace/certs/router-key"
        key_passphrase = "phrase"
        ssh_host_fingerprint_sha256 = fake_host_key_fingerprint()
        port = 22
        timeout = 5.0

    return Settings()
