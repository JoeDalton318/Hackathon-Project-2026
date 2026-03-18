from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.ws_manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/documents/{document_id}")
async def websocket_document(document_id: str, websocket: WebSocket):
    await ws_manager.connect(document_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(document_id, websocket)