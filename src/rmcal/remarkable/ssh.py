"""SSH/SFTP connection wrapper for reMarkable tablets."""

from __future__ import annotations

import io
from pathlib import Path

import paramiko

from rmcal.models import RemarkableConfig

XOCHITL_DIR = "/home/root/.local/share/remarkable/xochitl"


class RemarkableSSH:
    """Manages SSH/SFTP connection to a reMarkable tablet."""

    def __init__(self, config: RemarkableConfig) -> None:
        self.config = config
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._sftp: paramiko.SFTPClient | None = None

        connect_kwargs: dict = {
            "hostname": config.host,
            "username": config.user,
            "timeout": 10,
        }

        # Determine if auth is a password or SSH key path
        auth = config.auth
        if auth and Path(auth).expanduser().is_file():
            connect_kwargs["key_filename"] = str(Path(auth).expanduser())
        elif auth:
            connect_kwargs["password"] = auth

        self.client.connect(**connect_kwargs)

    @property
    def sftp(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            self._sftp = self.client.open_sftp()
        return self._sftp

    def exec_command(self, cmd: str) -> str:
        """Execute a command and return stdout."""
        _, stdout, stderr = self.client.exec_command(cmd)
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode()
        if exit_code != 0:
            err = stderr.read().decode()
            raise RuntimeError(f"Command failed (exit {exit_code}): {cmd}\n{err}")
        return output

    def read_file(self, remote_path: str) -> str:
        """Read a text file from the device."""
        with self.sftp.open(remote_path, "r") as f:
            return f.read().decode()

    def write_file(self, remote_path: str, content: str) -> None:
        """Write a text file to the device."""
        with self.sftp.open(remote_path, "w") as f:
            f.write(content)

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        """Upload a local file to the device."""
        self.sftp.put(str(local_path), remote_path)

    def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists on the device."""
        try:
            self.sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False

    def mkdir(self, remote_path: str) -> None:
        """Create a directory on the device (no error if exists)."""
        try:
            self.sftp.mkdir(remote_path)
        except OSError:
            pass  # Already exists

    def listdir(self, remote_path: str) -> list[str]:
        """List files in a directory on the device."""
        return self.sftp.listdir(remote_path)

    def restart_xochitl(self) -> None:
        """Restart the xochitl UI service to pick up file changes."""
        self.exec_command("systemctl restart xochitl")

    def close(self) -> None:
        if self._sftp:
            self._sftp.close()
        self.client.close()

    def __enter__(self) -> RemarkableSSH:
        return self

    def __exit__(self, *args) -> None:
        self.close()
