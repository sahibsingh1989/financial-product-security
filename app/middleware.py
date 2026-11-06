"""Bound the body before parsing; count actual bytes, including streamed bodies."""

import json
from email.message import Message

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

MAX_BODY_BYTES = 4096


def reject_constant(_value: str) -> None:
    raise ValueError("Nonstandard JSON number")


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                await JSONResponse(
                    {"detail": "Request body too large"}, status_code=413
                )(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        try:
            text = body.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            await JSONResponse(
                {"detail": "Invalid UTF-8 request body"}, status_code=400
            )(scope, receive, send)
            return
        headers = dict(scope["headers"])
        media_type = Message()
        media_type["content-type"] = headers.get(
            b"content-type", b"application/json"
        ).decode("latin-1")
        charset = media_type.get_content_charset()
        if charset is not None and charset not in {"utf-8", "utf8"}:
            await JSONResponse(
                {"detail": "Invalid UTF-8 request body"}, status_code=400
            )(scope, receive, send)
            return
        content_type = (
            headers.get(b"content-type", b"application/json")
            .split(b";")[0]
            .strip()
            .lower()
        )
        if body and (
            content_type == b"application/json" or content_type.endswith(b"+json")
        ):
            try:
                # Passing bytes would let Python silently autodetect UTF-16/32.
                json.loads(text, parse_constant=reject_constant)
            except (ValueError, RecursionError):
                await JSONResponse({"detail": "Invalid request body"}, status_code=422)(
                    scope, receive, send
                )
                return

        replayed = False

        async def replay() -> dict:
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
