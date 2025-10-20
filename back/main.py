from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from chat.chat import user_send_message, get_messages
from pydantic import BaseModel

# serve with: uvicorn main:app --reload --port 8000


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class MessagePydantic(BaseModel):
    role: str
    content: str

class MessagesPydantic(BaseModel):
    messages: list[MessagePydantic]

@app.get("/chat/{claudy_name}")
def get_messages_endpoint(claudy_name: str):
    stream_context = get_messages(claudy_name)
    return MessagesPydantic(messages=stream_context)

@app.post("/chat/{claudy_name}")
def chat_endpoint(claudy_name: str, message: MessagePydantic):
    claudy_messages = user_send_message(claudy_name, message.model_dump())
    return MessagesPydantic(messages=claudy_messages)
