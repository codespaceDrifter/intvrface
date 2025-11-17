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
            request_type = data_dict.get('request_type')
            claudy_name = data_dict.get('claudy_name')
            user_message = data_dict.get('user_message')

            match request_type:
                case 'CREATE_message':
                    CREATE_message(claudy_name, user_message)
                case 'READ_messages':
                    READ_messages(claudy_name)
                case 'START_agent':
                    await START_agent(claudy_name)
                case 'STOP_agent':
                    await STOP_agent(claudy_name)
            

    except WebSocketDisconnect as e:
        print(f"WebSocketDisconnect: ", e.code, flush=True)
    finally:
        print("connection closed", flush=True)