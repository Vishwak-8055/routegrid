"""In-memory WebSocket connection registry + broadcast helper.

A single process's worth of state -- fine for a demo/single-instance
deployment. A production multi-instance deployment would back this with
Redis pub/sub instead; the broadcast() call site wouldn't need to change.
"""
from __future__ import annotations

import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, payload: dict) -> None:
        dead = []
        message = json.dumps(payload, default=str)
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
