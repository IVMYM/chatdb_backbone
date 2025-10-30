# app.py
import os
import json
from datetime import datetime, timedelta
from typing import Optional
import asyncio
import os
import json
from dotenv import load_dotenv
import httpx
from fastmcp import Client
from fastmcp.client.transports import SSETransport
from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header, Form,WebSocket, WebSocketDisconnect,Query
from fastapi.responses import StreamingResponse
from user import UserCreate, TokenResponse # 导入 user 模块以获取 UserCreate 和 TokenResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
from llmapi4 import mcp_main   ,create_ai_ws_url
# SQLAlchemy (同步) 简单版
from sqlalchemy import Column, Integer, String, Boolean, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import websockets 
import uuid
load_dotenv()

# LLM / MCP related envs (保留你原来的)
MODEL = os.getenv("MODEL", "Qwen/Qwen3-14B")
MODEL_SECOND_PASS = os.getenv("MODEL_SECOND_PASS", MODEL)
API_KEY = os.getenv('OAI_API_KEY')
SSE_URL = os.getenv('SSE_URL', 'http://localhost:19068/sse')
LLM_API = os.getenv('BASE_URL', "https://api.siliconflow.cn/v1/chat/completions")
FIRST_PASS_TIMEOUT = float(os.getenv('FIRST_PASS_TIMEOUT', 10.0))
APP_ID = os.getenv("APP_ID", "0FCBBC4DB13541E8AE20")
ASSISTANT_CODE = os.getenv("ASSISTANT_CODE", "scene@1971108944157155328")
# JWT config
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 60))

# SQLite DB path
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./users.db")
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
# Header Information
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
# ------------------------------
# Password hashing
# ------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ------------------------------
# SQLAlchemy setup
# ------------------------------
Base = declarative_base()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(300), nullable=False)
    is_active = Column(Boolean, default=True)

# Create tables at startup
def create_db_and_tables():
    Base.metadata.create_all(bind=engine)

 
# ------------------------------
# JWT helpers
# ------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_jwt_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid JWT: missing subject")
        return username
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")

# ------------------------------
# DB utility
# ------------------------------
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, username: str, password: str) -> User:
    hashed = pwd_context.hash(password)
    db_user = User(username=username, hashed_password=hashed, is_active=True)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

#提取工具调用结果
def extract_tool_result(result):
    """Attempt to extract JSON content from fastmcp ClientCallResult"""
    try:
        if result.content:
            raw_text = result.content[0].text
            return json.loads(raw_text)
    except Exception as e:
        print("Failed to parse tool result:", e)
    return str(result)  # Fallback
# ------------------------------
# FastAPI 初始化
# ------------------------------
app = FastAPI(title="Streaming DB Inspector (JWT + SQLite Users)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:19070"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 建表
@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# ------------------------------
# Auth Dependency
# ------------------------------
async def get_current_active_user(authorization: str = Header(None)):
    """
    从 Authorization: Bearer <token> 中解析并验证 JWT，
    并返回用户名（subject）。如果需要，可以查询 DB 检查用户仍存在/激活。
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    token = parts[1]
    username = verify_jwt_token(token)
    # 可选：检查用户在 DB 中是否仍存在并激活
    db = SessionLocal()
    try:
        user = get_user_by_username(db, username)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="用户不存在或已禁用")
        return user
    finally:
        db.close()

# ------------------------------
# Auth routes: register / login
# ------------------------------
@app.post("/register", status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """
    注册新用户（简单实现）。生产请添加邮箱验证、复杂密码策略等。
    """
    username = payload.username.strip()
    password = payload.password
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")
    existing = get_user_by_username(db, username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    user = create_user(db, username, password)
    return {"id": user.id, "username": user.username}

@app.post("/api/login", response_model=TokenResponse)
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """
    登录并返回 JWT。
    """
    user = get_user_by_username(db, username)
    print("Login attempt for user:", user )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    access_token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=access_token, expires_in=JWT_EXPIRE_MINUTES * 60)

# ------------------------------
# Protected ping
# ------------------------------
@app.get("/ping")
def ping(user: User = Depends(get_current_active_user)):
    return {"status": "ok", "user": user.username}


# ------------------------------
# SSE 流式接口（受保护）-deprecated
# ------------------------------
@app.get("/service/true_dbinspect")
def stream_query(question: str, user: User = Depends(get_current_active_user)):
    """
    SSE 流式接口，必须带 Authorization: Bearer <JWT>
    """
    # NOTE: 请把你现有的 mcp_main 函数替换调用
    # 下面示例演示如何包装：如果 mcp_main 是 async generator， StreamingResponse 能直接使用它。
    try:
        generator = mcp_main(question)  
    except NameError:
        # 临时 fallback，如果你还没粘回 mcp_main，以便本文件能运行
        async def fallback_gen():
            yield "data: ### 错误：mcp_main 未找到，请将原始实现粘回此文件。\n\n"
        generator = fallback_gen()
    return StreamingResponse(generator, media_type="text/event-stream")

#-----------
#聚智ws会话接口
#-----------
@app.websocket("/ws/ai-question")
async def ai_question_websocket(
    websocket: WebSocket,
    session_id: str = Query(..., description="前端会话ID")
):
    await websocket.accept()
    ai_ws = None
    try:
        # 1. 接收前端消息
        data = await websocket.receive_text()
        req = json.loads(data)
        question = req.get("question", "默认问题")
        print(f"📥 FastAPI收到前端消息：session_id={session_id}, question={question}")

        # 2. 连接Node.js（优化配置）
        # ai_ws_url = f'ws://127.0.0.1:3001/ws/server-ai?session_id={session_id}'
        # 生产websocket连接
        ai_ws_url = await create_ai_ws_url()
        print(f"🚀 FastAPI正在连接：{ai_ws_url}")
        ai_ws = await websockets.connect(
            ai_ws_url,
            ping_interval=15,  # 延长ping间隔，减少干扰
            ping_timeout=45,
            open_timeout=10,
            close_timeout=10  # 关键：设置关闭超时，等待关闭帧
        )
        print(f"✅ FastAPI已连接：{ai_ws_url}")

        # 3. 发送payload
        payload = {
            "question": question,
            "sessionId": session_id
        }
        payload_str = json.dumps(payload, ensure_ascii=False)
        await ai_ws.send(payload_str)
 

        # 4. 接收响应（优化循环逻辑）
        while True:
            try:
                # 延长超时时间，确保所有流式数据接收完成
                ai_response = await asyncio.wait_for(ai_ws.recv(), timeout=20.0)
                ai_data = json.loads(ai_response)
                print(f"📥 FastAPI收到响应[${session_id}]：status={ai_data['status']}, content={ai_data['content'][:20]}...")

                await websocket.send_text(json.dumps({
                    "status": ai_data["status"],
                    "content": ai_data["content"]
                }))

                # 收到结束信号后，主动等待关闭帧
                if ai_data["status"] == 2:
                    print(f"⏳ 等待Node.js关闭连接[${session_id}]")
                    # 等待Node.js发送关闭帧（最多等5秒）
                    try:
                        await asyncio.wait_for(ai_ws.recv(), timeout=5.0)
                    except asyncio.TimeoutError:
                        # 没收到额外消息，正常关闭
                        pass
                    print(f"✅ 会话[${session_id}]正常结束")
                    break

            except asyncio.TimeoutError:
                error_msg = f"接收响应超时（20秒）"
                print(f"⌛ {error_msg}")
                await websocket.send_text(json.dumps({
                    "status": -1,
                    "content": error_msg
                }))
                break
            except websockets.exceptions.ConnectionClosedOK:
                # 关键修复：捕获正常关闭异常（收到关闭帧）
                print(f"✅ Node.js正常关闭连接[${session_id}]")
                break
            except websockets.exceptions.ConnectionClosedError as e:
                # 捕获异常关闭
                error_msg = f"连接异常关闭：{str(e)}"
                print(f"❌ {error_msg}")
                await websocket.send_text(json.dumps({
                    "status": -1,
                    "content": error_msg
                }))
                break
            except Exception as recv_err:
                error_msg = f"接收消息失败：{str(recv_err)}"
                print(f"❌ {error_msg}")
                await websocket.send_text(json.dumps({
                    "status": -1,
                    "content": error_msg
                }))
                break

    except WebSocketDisconnect:
        print(f"🔌 前端主动断开会话：{session_id}")
    except Exception as e:
        error_msg = f"处理失败：{str(e)}"
        print(f"❌ {error_msg}")
        await websocket.send_text(json.dumps({
            "status": -1,
            "content": error_msg
        }))
    finally:
        # 关键修复：正确关闭Node.js连接
        if ai_ws :
            try:
                # 发送关闭帧给Node.js
                await ai_ws.close(code=1000, reason="会话结束")
                print(f"✅ FastAPI关闭ws连接：{session_id}")
            except Exception as e:
                print(f"❌ 关闭ws连接失败：{str(e)}")
        # 延迟关闭前端连接
        await asyncio.sleep(1.5)
        await websocket.close()