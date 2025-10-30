from sqlmodel import Session, select
from models import User, DBConfig
from passlib.context import CryptContext
from datetime import datetime

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    """
    计算密码的哈希值。
    注意：为了遵守 bcrypt 的 72 字节限制，我们确保密码在哈希前被截断。
    """
    # 修复：将密码编码为 bytes，并安全地截断到 72 字节，以避免 ValueError。
    password_bytes = password.encode('utf8')
    return pwd_ctx.hash(password_bytes[:72])

def verify_password(plain, hashed):
    return pwd_ctx.verify(plain, hashed)

def init_db(engine):
    with Session(engine) as s:
        q = s.exec(select(User)).first()
        if not q:
            # 这里的 "admin123" 密码长度是安全的 (8 字节)
            admin = User(username="admin", full_name="Administrator", email="admin@example.com",
                         hashed_password=get_password_hash("admin123"), is_superuser=True)
            s.add(admin)
            s.commit()

def get_user_by_username(db: Session, username: str):
    return db.exec(select(User).where(User.username == username)).first()

def create_user(db: Session, username: str, password: str, email=None, full_name=None):
    user = User(username=username, hashed_password=get_password_hash(password), email=email, full_name=full_name)
    db.add(user); db.commit(); db.refresh(user)
    return user

def get_db_config(db: Session):
    cfg = db.exec(select(DBConfig)).first()
    return cfg

def set_db_config(db: Session, target_url: str):
    cfg = db.exec(select(DBConfig)).first()
    if not cfg:
        cfg = DBConfig(target_url=target_url, updated_at=datetime.utcnow())
        db.add(cfg)
    else:
        cfg.target_url = target_url
        cfg.updated_at = datetime.utcnow()
    db.commit(); db.refresh(cfg)
    return cfg
