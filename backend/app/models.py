from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    full_name: Optional[str] = None
    email: Optional[str] = None
    hashed_password: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DBConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    target_url: Optional[str] = None
    updated_at: Optional[datetime] = None
