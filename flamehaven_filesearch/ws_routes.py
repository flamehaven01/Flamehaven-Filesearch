"""
WebSocket streaming endpoint for FLAMEHAVEN FileSearch v2.0.

Provides real-time token-by-token search results over WebSocket.

Protocol (client -> server, first message):
    {"token": "sk_live_...", "query": "...", "store": "default",
     "model": "...", "max_tokens": 1000, "temperature": 0.7}

Protocol (server -> client, streamed):
    {"type": "chunk",   "text": "...partial answer..."}
    {"type": "done",    "query": "...", "store": "...", "total_chars": 123}
    {"type": "error",   "message": "..."}
    {"type": "auth_error", "message": "Invalid or missing token"}
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .auth import get_key_manager

if TYPE_CHECKING:
    from .core import FlamehavenFileSearch

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# Injected by api.py after searcher initialisation
_searcher: Optional["FlamehavenFileSearch"] = None


def set_searcher(searcher: "FlamehavenFileSearch") -> None:
    """Register the shared FlamehavenFileSearch instance."""
    global _searcher
    _searcher = searcher


def _validate_token(token: str) -> bool:
    """Return True if token belongs to a valid, active API key."""
    if not token:
        return False
    key_manager = get_key_manager()
    info = key_manager.validate_key(token)
    return info is not None


@router.websocket("/ws/search")
async def ws_search(websocket: WebSocket):
    """
    Stream search results over WebSocket.

    Connect, then send a single JSON message with 'token' and 'query'.
    Receive streaming chunks until a 'done' or 'error' message.
    """
    await websocket.accept()

    try:
        # --- Auth handshake ---
        try:
            init = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        except asyncio.TimeoutError:
            await websocket.send_json(
                {"type": "auth_error", "message": "Handshake timeout"}
            )
            await websocket.close(code=1008)
            return

        token = init.get("token", "")
        if not _validate_token(token):
            await websocket.send_json(
                {"type": "auth_error", "message": "Invalid or missing token"}
            )
            await websocket.close(code=1008)
            return

        if _searcher is None:
            await websocket.send_json(
                {"type": "error", "message": "Service not initialised"}
            )
            await websocket.close(code=1011)
            return

        query: str = init.get("query", "").strip()
        if not query:
            await websocket.send_json({"type": "error", "message": "query is required"})
            await websocket.close(code=1003)
            return

        store: str = init.get("store", "default")
        model: Optional[str] = init.get("model") or None
        max_tokens: Optional[int] = init.get("max_tokens") or None
        temperature: Optional[float] = init.get("temperature")

        # --- Stream via thread executor ---
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _run_stream():
            try:
                for chunk_text in _searcher.search_stream(
                    query=query,
                    store_name=store,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ):
                    asyncio.run_coroutine_threadsafe(
                        queue.put(("chunk", chunk_text)), loop
                    )
                asyncio.run_coroutine_threadsafe(queue.put(("done", None)), loop)
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(queue.put(("error", str(exc))), loop)

        loop.run_in_executor(None, _run_stream)

        total_chars = 0
        while True:
            kind, payload = await queue.get()

            if kind == "chunk":
                total_chars += len(payload)
                await websocket.send_json({"type": "chunk", "text": payload})

            elif kind == "done":
                await websocket.send_json(
                    {
                        "type": "done",
                        "query": query,
                        "store": store,
                        "total_chars": total_chars,
                    }
                )
                break

            elif kind == "error":
                await websocket.send_json({"type": "error", "message": payload})
                break

    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected")
    except Exception as exc:
        logger.error("[WS] Unexpected error: %s", exc)
        try:
            await websocket.send_json(
                {"type": "error", "message": "Internal server error"}
            )
        except Exception as send_exc:
            logger.debug("[WS] send_json failed during error cleanup: %s", send_exc)
    finally:
        try:
            await websocket.close()
        except Exception as close_exc:
            logger.debug("[WS] close() failed: %s", close_exc)
