from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agent.io import CREATE_message, READ_message, READ_messages
from pydantic import BaseModel
from fastapi import WebSocket
from agent.socket_manager import socket_manager 
import json
from agent.work import START_agent, STOP_agent
from fastapi.websockets import WebSocketDisconnect


# serve with: uvicorn main:app --reload --port 8000


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    socket_manager.set_connection(websocket)
    await websocket.accept()
    # the blocks the main thread. so all agents needs to run in side threads

    try:
        while True:
            data = await websocket.receive_text()
            data_dict = json.loads(data)
            
            if data_dict['type'] == 'CREATE_message':
                CREATE_message(data_dict)

            elif data_dict['type'] == 'READ_messages':
                READ_messages(data_dict)

            elif data_dict['type'] == 'START_agent':
                await START_agent(data_dict)

            elif data_dict['type'] == 'STOP_agent':
                await STOP_agent(data_dict)
    except WebSocketDisconnect as e:
        print(f"WebSocketDisconnect: ", e.code, flush=True)
    finally:
        print("connection closed", flush=True)