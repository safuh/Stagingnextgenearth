#!/usr/bin/env python3
"""Run a loopback-only ODK Central protocol simulator with synthetic climate data."""

from __future__ import annotations

import argparse
import ipaddress
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/odk/climate-observation/sample_odata_submissions.json"
FORM_ID = "nextgen_climate_observation"
FORM = {
    "xmlFormId": FORM_ID,
    "name": "NextGen Climate Observation (synthetic demo)",
    "version": "1",
    "state": "open",
}


class MockCentralServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(
    *, email: str, password: str, project_id: int, page_size: int
) -> type[BaseHTTPRequestHandler]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    submissions = fixture.get("value")
    if not isinstance(submissions, list) or not all(isinstance(row, dict) for row in submissions):
        raise ValueError("Synthetic OData fixture must contain a list of submission objects")
    token = "nextgen-local-mock-session"

    class Handler(BaseHTTPRequestHandler):
        server_version = "NextGenMockCentral/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            # Session tokens appear in DELETE paths; never log request paths or credentials.
            return

        def _send_json(self, status_code: int, payload: object) -> None:
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _authorized(self) -> bool:
            return self.headers.get("Authorization") == f"Bearer {token}"

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"status": "ok", "mode": "synthetic-only"})
                return
            forms_path = f"/v1/projects/{project_id}/forms"
            if parsed.path == forms_path:
                if not self._authorized():
                    self._send_json(401, {"message": "unauthorized"})
                    return
                self._send_json(200, [FORM])
                return
            submissions_path = f"/v1/projects/{project_id}/forms/{FORM_ID}.svc/Submissions"
            if parsed.path == submissions_path:
                if not self._authorized():
                    self._send_json(401, {"message": "unauthorized"})
                    return
                query = parse_qs(parsed.query)
                raw_offset = query.get("$skiptoken", ["0"])[0]
                try:
                    offset = int(raw_offset)
                except ValueError:
                    self._send_json(400, {"message": "invalid skip token"})
                    return
                if offset < 0 or offset > len(submissions):
                    self._send_json(400, {"message": "invalid skip token"})
                    return
                page = submissions[offset : offset + page_size]
                next_offset = offset + len(page)
                payload: dict[str, object] = {"value": page}
                if next_offset < len(submissions):
                    host = self.headers.get("Host", "127.0.0.1")
                    payload["@odata.nextLink"] = (
                        f"http://{host}{submissions_path}?$skiptoken={next_offset}"
                    )
                self._send_json(200, payload)
                return
            self._send_json(404, {"message": "not found"})

        def do_POST(self) -> None:
            if urlsplit(self.path).path != "/v1/sessions":
                self._send_json(404, {"message": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
            except (ValueError, json.JSONDecodeError):
                self._send_json(400, {"message": "invalid JSON"})
                return
            if (
                not isinstance(payload, dict)
                or payload.get("email") != email
                or payload.get("password") != password
            ):
                self._send_json(401, {"message": "invalid local demo credentials"})
                return
            self._send_json(200, {"token": token})

        def do_DELETE(self) -> None:
            if urlsplit(self.path).path == f"/v1/sessions/{quote(token, safe='')}":
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._send_json(404, {"message": "session not found"})

    return Handler


def build_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    email: str = "odk-demo@example.test",
    password: str = "local-demo-only",
    project_id: int = 22,
    page_size: int = 1,
) -> MockCentralServer:
    address = ipaddress.ip_address(host)
    if not address.is_loopback:
        raise ValueError("The synthetic ODK Central simulator must bind to loopback only")
    if page_size < 1 or page_size > 100:
        raise ValueError("page_size must be between 1 and 100")
    return MockCentralServer(
        (host, port),
        make_handler(email=email, password=password, project_id=project_id, page_size=page_size),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Loopback address only")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--project-id", type=int, default=22)
    parser.add_argument("--page-size", type=int, default=1)
    parser.add_argument("--email", default="odk-demo@example.test")
    parser.add_argument("--password", default="local-demo-only")
    args = parser.parse_args()
    server = build_server(
        args.host,
        args.port,
        email=args.email,
        password=args.password,
        project_id=args.project_id,
        page_size=args.page_size,
    )
    print(f"Synthetic ODK Central listening on http://{args.host}:{server.server_port}")
    print(f"Project ID: {args.project_id}; form: {FORM_ID}; synthetic submissions: 2")
    print("Credentials are local demo values only. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping synthetic ODK Central.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
