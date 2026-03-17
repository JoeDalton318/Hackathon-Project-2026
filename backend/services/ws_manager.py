from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, document_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(document_id, []).append(websocket)

    def disconnect(self, document_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(document_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self._connections.pop(document_id, None)

    async def broadcast(self, document_id: str, payload: dict) -> None:
        connections = self._connections.get(document_id, [])
        for websocket in list(connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(document_id, websocket)


ws_manager = ConnectionManager()
