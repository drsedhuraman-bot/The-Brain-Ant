from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from ..orchestration.streaming import StreamingCoordinator

router = APIRouter()


@router.websocket("/ws/{task_id}")
async def task_stream(websocket: WebSocket, task_id: str):
    streaming: StreamingCoordinator = websocket.app.state.streaming
    await websocket.accept()
    queue = streaming.subscribe(task_id)
    try:
        while True:
            msg = await queue.get()
            if msg is None:
                break
            await websocket.send_json(msg.model_dump())
    except WebSocketDisconnect:
        pass
    finally:
        streaming.unsubscribe(task_id, queue)
        try:
            await websocket.close()
        except Exception:
            pass
