"""
AAROGYA-SHIELD: WebSocket Live Stream Manager
Maintains concurrent client WebSocket connections and broadcasts real-time
telemetry, feature derivations, ML predictions, risk escalations, and alerts.
"""

from typing import List, Dict, Any
from fastapi import WebSocket

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WebSocket] Client connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WebSocket] Client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

ws_manager = WebSocketManager()
