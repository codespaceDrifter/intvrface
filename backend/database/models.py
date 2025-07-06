from 

class User(Base):
  __tablename__ = "users"
  id = Column(Integer, primary_key=True, autoincrement=True)
  sub = Column(String, nullable=False, unique=True)
  name = Column(String(50))
  chats = relationship("Chat", back_populates="user")

class Chat(Base):
  __tablename__ = "chats"
  id = Column(Integer, primary_key=True, autoincrement=True)
  user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
  messages = relationship("Message", back_populates="chat")
  name = Column(String(50))
  user = relationship("User", back_populates="chats")

class Message(Base):
  __tablename__ = "messages"
  id = Column(Integer, primary_key=True, autoincrement=True)
  core = Column(String, nullable=False)
  is_user = Column(Boolean, nullable=False)
  # index = true creates a map between a chat and their messages making "get all message" reads from a chat much faster
  # without it the operation would need to read and check every message in the database
  chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False, index=True)
  chat = relationship("Chat", back_populates="messages")

