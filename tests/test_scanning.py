"""Tests for the ClamAV INSTREAM adapter."""

import struct

from stagingnextgenearth.scanning import ClamAVScanner


class FakeConnection:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.sent = bytearray()
        self.timeout: float | None = None

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)

    def recv(self, size: int) -> bytes:
        return self.response


def test_clamav_scanner_streams_content_and_accepts_clean_verdict(monkeypatch) -> None:
    connection = FakeConnection(b"stream: OK\\0")
    monkeypatch.setattr(
        "stagingnextgenearth.scanning.socket.create_connection",
        lambda address, timeout: connection,
    )
    scanner = ClamAVScanner(host="127.0.0.1")

    assert scanner.scan(b"sample") is True
    assert connection.sent.startswith(b"zINSTREAM\\0")
    assert connection.sent.endswith(struct.pack("!I", 0))
    assert connection.timeout == 30


def test_clamav_scanner_rejects_found_verdict(monkeypatch) -> None:
    connection = FakeConnection(b"stream: Eicar-Test-Signature FOUND\\0")
    monkeypatch.setattr(
        "stagingnextgenearth.scanning.socket.create_connection",
        lambda address, timeout: connection,
    )

    assert ClamAVScanner(host="127.0.0.1").scan(b"sample") is False
