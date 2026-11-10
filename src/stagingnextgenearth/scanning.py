"""Malware scanning adapters for private research dataset files."""

import socket
import struct
from typing import Protocol


class FileScanner(Protocol):
    """Contract for a scanner that returns True only for a clean file."""

    def scan(self, content: bytes) -> bool: ...


class ClamAVScanner:
    """ClamAV TCP INSTREAM client; fails closed on protocol or service errors."""

    def __init__(self, *, host: str, port: int = 3310, timeout_seconds: float = 30) -> None:
        if not host:
            raise ValueError("ClamAV host is required")
        if not 1 <= port <= 65535:
            raise ValueError("ClamAV port must be between 1 and 65535")
        if timeout_seconds <= 0:
            raise ValueError("ClamAV timeout must be positive")
        self._host = host
        self._port = port
        self._timeout = timeout_seconds

    def scan(self, content: bytes) -> bool:
        """Send bytes using INSTREAM and return False only for a FOUND verdict."""
        with socket.create_connection(
            (self._host, self._port), timeout=self._timeout
        ) as connection:
            connection.settimeout(self._timeout)
            connection.sendall(b"zINSTREAM\0")
            for offset in range(0, len(content), 64 * 1024):
                chunk = content[offset : offset + 64 * 1024]
                connection.sendall(struct.pack("!I", len(chunk)))
                connection.sendall(chunk)
            connection.sendall(struct.pack("!I", 0))
            response = bytearray()
            while not response.endswith(b"\0"):
                chunk = connection.recv(4096)
                if not chunk:
                    raise RuntimeError("ClamAV closed the connection without a verdict")
                response.extend(chunk)
                if len(response) > 4096:
                    raise RuntimeError("ClamAV response exceeded the protocol limit")
        verdict = response.decode("utf-8", errors="replace").strip("\0")
        if verdict.endswith(": OK"):
            return True
        if verdict.endswith(" FOUND"):
            return False
        raise RuntimeError("ClamAV returned an error or unrecognised verdict")
