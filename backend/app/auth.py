import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from datetime import datetime, timedelta
from sqlmodel import Session
from crud import get_user_by_username, create_user, verify_password
from schemas import Token, UserCreate, DBConfigIn
from deps import get_db

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

SECRET_KEY = os.getenv("JWT_SECRET", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60*24

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/register", status_code=201)
def register(u: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_username(db, u.username):
        raise HTTPException(status_code=400, detail="username exists")
    user = create_user(db, u.username, u.password, u.email, u.full_name)
    return {"id": user.id, "username": user.username}

from fastapi import Security

def get_current_active_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user

# admin endpoints
from crud import get_db_config, set_db_config
from sqlmodel import Session

@router.get("/me")
def me(current=Depends(get_current_active_user)):
    return {"username": current.username, "email": current.email, "is_superuser": current.is_superuser}

@router.get("/admin/users")
def list_users(db: Session = Depends(get_db), current=Depends(get_current_active_user)):
    if not current.is_superuser:
        raise HTTPException(status_code=403, detail="superuser only")
    users = db.exec("SELECT id, username, email, is_active, is_superuser FROM user").all()
    return users

@router.post("/admin/db-config")
def set_dbcfg(cfg: DBConfigIn, db: Session = Depends(get_db), current=Depends(get_current_active_user)):
    if not current.is_superuser:
        raise HTTPException(status_code=403, detail="superuser only")
    return set_db_config(db, cfg.target_url)

@router.get("/admin/db-config")
def get_dbcfg(db: Session = Depends(get_db), current=Depends(get_current_active_user)):
    if not current.is_superuser:
        raise HTTPException(status_code=403, detail="superuser only")
    cfg = get_db_config(db)
    return cfg or {}
