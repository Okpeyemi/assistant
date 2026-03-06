import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from agent import NavigationAgent

app = FastAPI(title="Assistant Démarches Bénin", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Assistant Démarches Bénin — API opérationnelle"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    agent = NavigationAgent(websocket)

    try:
        await agent.initialize()
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "user_message":
                text = data.get("text", "").strip()
                if text:
                    await agent.process_message(text)
            elif data.get("type") == "field_answer":
                field_id = data.get("field_id", "")
                value = data.get("value", "").strip()
                if value:
                    await agent.receive_field_answer(field_id, value)
            elif data.get("type") == "document":
                doc_data = data.get("data", "")
                mime_type = data.get("mime_type", "image/jpeg")
                if doc_data:
                    await agent.receive_document(doc_data, mime_type)
    except WebSocketDisconnect:
        print("Client déconnecté")
    except Exception as e:
        print(f"Erreur WebSocket: {e}")
    finally:
        await agent.close()
