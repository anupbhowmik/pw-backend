"""Request-logging middleware with request_id generation (pure ASGI)."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Pure ASGI middleware — avoids BaseHTTPMiddleware thread issues with async DB."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:12]
        scope.setdefault("state", {})["request_id"] = request_id

        request = Request(scope)
        t0 = time.perf_counter()
        logger.info("[%s] %s %s", request_id, request.method, request.url.path)

        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

        elapsed = int((time.perf_counter() - t0) * 1000)
        logger.info("[%s] %s %dms", request_id, status_code, elapsed)
