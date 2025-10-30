import os
from sqlmodel import Session, create_engine
from typing import Generator

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")
engine = create_engine(DATABASE_URL, echo=False)

def get_db() -> Generator:
    with Session(engine) as s:
        yield s
