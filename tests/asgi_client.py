"""Minimal ASGI client for API tests.

``fastapi.testclient.TestClient`` requires httpx, which is not installed in this
environment, so these tests call the ASGI application directly instead.  Real routing,
path and query parsing, dependency injection, status codes, JSON serialization and
background tasks all execute; only the HTTP transport is replaced.

The application's lifespan is deliberately *not* run, so importing the API in a test
never touches the development database or starts the schedule runner thread.
"""

from __future__ import annotations

import asyncio
import json
from urllib.parse import urlencode


class Response:
    """Just enough of a response object for assertions."""

    def __init__(self, status: int, headers: dict[str, str], body: bytes):
        self.status_code, self.headers, self.body = status, headers, body

    def json(self):
        return json.loads(self.body) if self.body else None

    @property
    def text(self) -> str:
        return self.body.decode()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Response {self.status_code} {self.body[:200]!r}>"


class AsgiClient:
    """Synchronous caller for a FastAPI/Starlette application."""

    def __init__(self, app, *, headers: dict[str, str] | None = None):
        self.app = app
        self.default_headers = dict(headers or {})

    def request(self, method: str, path: str, *, params: dict | None = None,
                json_body: object | None = None, headers: dict[str, str] | None = None) -> Response:
        query = urlencode({key: value for key, value in (params or {}).items() if value is not None})
        payload = json.dumps(json_body).encode() if json_body is not None else b""
        merged = {**self.default_headers, **(headers or {})}
        if payload:
            merged.setdefault("content-type", "application/json")
            merged["content-length"] = str(len(payload))
        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
            "method": method.upper(), "path": path, "raw_path": path.encode(),
            "query_string": query.encode(), "root_path": "", "scheme": "http",
            "headers": [(key.lower().encode(), str(value).encode()) for key, value in merged.items()],
            "client": ("testclient", 50000), "server": ("testserver", 80),
        }
        sent: list[dict] = []

        async def receive():
            return {"type": "http.request", "body": payload, "more_body": False}

        async def send(message):
            sent.append(message)

        asyncio.run(self.app(scope, receive, send))
        start = next(message for message in sent if message["type"] == "http.response.start")
        body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
        response_headers = {key.decode().lower(): value.decode() for key, value in start.get("headers", [])}
        return Response(start["status"], response_headers, body)

    def get(self, path: str, **kwargs) -> Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Response:
        return self.request("DELETE", path, **kwargs)
