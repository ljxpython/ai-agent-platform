from typing import Generator

from app.db.session import SessionLocal
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()
