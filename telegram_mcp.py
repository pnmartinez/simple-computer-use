#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import pathlib
import sys
import uuid
import http.client
from typing import Optional

from mcp.server.fastmcp import FastMCP

# IMPORTANT: no stdout logs in STDIO servers
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger("telegram_mcp")

mcp = FastMCP("telegram")

TELEGRAM_API_HOST = os.getenv("TELEGRAM_API_HOST", "api.telegram.org")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID_DEFAULT = os.getenv("TELEGRAM_CHAT_ID", "")
ALLOWED_ROOT = os.getenv("TELEGRAM_ALLOWED_ROOT", "").strip()

CHUNK_SIZE = 1024 * 1024


def _ensure_allowed(path: pathlib.Path) -> None:
    if not ALLOWED_ROOT:
        return
    root = pathlib.Path(ALLOWED_ROOT).expanduser().resolve()
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(root)
    except Exception as exc:
        raise ValueError(
            f"Path fuera de TELEGRAM_ALLOWED_ROOT: {resolved} (root={root})"
        ) from exc


def _multipart_lengths(
    boundary: str,
    fields: list[tuple[str, str]],
    file_field: str,
    filename: str,
) -> tuple[bytes, bytes]:
    boundary_bytes = boundary.encode()
    parts = []
    for key, value in fields:
        parts.append(
            b"--" + boundary_bytes + b"\r\n"
            + f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            + value.encode("utf-8")
            + b"\r\n"
        )
    file_header = (
        b"--" + boundary_bytes + b"\r\n"
        + f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode()
        + b"Content-Type: application/octet-stream\r\n\r\n"
    )
    closing = b"\r\n--" + boundary_bytes + b"--\r\n"
    prefix = b"".join(parts) + file_header
    suffix = closing
    return prefix, suffix


def _telegram_send_document_sync(
    token: str,
    chat_id: str,
    file_path: str,
    caption: Optional[str] = None,
    disable_notification: bool = False,
    protect_content: bool = False,
) -> dict:
    if not token:
        raise ValueError("Falta TELEGRAM_BOT_TOKEN (env) o token (param).")
    if not chat_id:
        raise ValueError("Falta TELEGRAM_CHAT_ID (env) o chat_id (param).")
    path = pathlib.Path(file_path).expanduser()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    _ensure_allowed(path)

    boundary = "mcp-" + uuid.uuid4().hex
    filename = path.name
    fields = [("chat_id", str(chat_id))]
    if caption:
        fields.append(("caption", caption))
    if disable_notification:
        fields.append(("disable_notification", "true"))
    if protect_content:
        fields.append(("protect_content", "true"))

    prefix, suffix = _multipart_lengths(boundary, fields, "document", filename)
    file_size = path.stat().st_size
    content_length = len(prefix) + file_size + len(suffix)

    conn = http.client.HTTPSConnection(TELEGRAM_API_HOST, timeout=120)
    request_path = f"/bot{token}/sendDocument"
    conn.putrequest("POST", request_path)
    conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
    conn.putheader("Content-Length", str(content_length))
    conn.endheaders()

    conn.send(prefix)
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            conn.send(chunk)
    conn.send(suffix)

    resp = conn.getresponse()
    body = resp.read()
    conn.close()

    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise RuntimeError(
            f"Respuesta no-JSON de Telegram: HTTP {resp.status} {resp.reason}: {body[:200]!r}"
        ) from exc

    if resp.status < 200 or resp.status >= 300 or not data.get("ok"):
        raise RuntimeError(f"Telegram error: HTTP {resp.status} {resp.reason}: {data}")

    return data


@mcp.tool()
async def send_document(
    file_path: str,
    caption: Optional[str] = None,
    chat_id: Optional[str] = None,
    disable_notification: bool = False,
    protect_content: bool = False,
) -> str:
    """Envía un archivo local a un chat de Telegram vía Bot API (sendDocument)."""
    token = TELEGRAM_BOT_TOKEN
    resolved_chat_id = chat_id or TELEGRAM_CHAT_ID_DEFAULT
    data = await asyncio.to_thread(
        _telegram_send_document_sync,
        token,
        resolved_chat_id,
        file_path,
        caption,
        disable_notification,
        protect_content,
    )
    msg = data.get("result", {})
    message_id = msg.get("message_id")
    doc = msg.get("document", {}) or {}
    sent_name = doc.get("file_name") or pathlib.Path(file_path).name
    sent_size = doc.get("file_size")
    return (
        "Enviado a Telegram. "
        f"message_id={message_id}, file_name={sent_name}, file_size={sent_size}"
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
