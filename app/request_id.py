"""Middleware ASGI murni untuk request ID."""

import re
import uuid

from starlette.types import ASGIApp, Receive, Scope, Send

REQ_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class RequestIDMiddleware:
    """Pure ASGI middleware untuk tracking request ID."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        req_id = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"x-request-id":
                val = value.decode("latin1", errors="ignore")
                if REQ_ID_PATTERN.match(val):
                    req_id = val
                break

        if not req_id:
            req_id = f"req_{uuid.uuid4().hex}"

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = req_id

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Hapus header x-request-id jika sudah ada, pasang yang valid dan konsisten
                filtered_headers = [
                    (name, val) for name, val in headers if name.lower() != b"x-request-id"
                ]
                filtered_headers.append((b"x-request-id", req_id.encode("latin1")))
                message["headers"] = filtered_headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
