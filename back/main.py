from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from chat.chat import CREATE_message, READ_message, READ_messages
from pydantic import BaseModel
from fastapi import WebSocket
from chat.socket_manager import socket_manager 
import json


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

    while True:
        data = await websocket.receive_text()
        data_dict = json.loads(data)
        
        if data_dict['type'] == 'CREATE_message':
            CREATE_message(data_dict)

        elif data_dict['type'] == 'READ_messages':
            READ_messages(data_dict)