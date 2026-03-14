from __future__ import annotations

from app.db import models  # noqa: F401
from app.db.base import Base
from sqlalchemy.engine import Engine


def create_core_tables(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
