from typing import List, Optional

from app.crud.base import CRUDBase
from app.models.value_mapping import ValueMapping
from app.schemas.value_mapping import ValueMappingCreate, ValueMappingUpdate
from sqlalchemy.orm import Session


class CRUDValueMapping(CRUDBase[ValueMapping, ValueMappingCreate, ValueMappingUpdate]):
    def get_by_column(
        self, db: Session, *, column_id: int, skip: int = 0, limit: int = 100
    ) -> List[ValueMapping]:
        return (
            db.query(ValueMapping)
            .filter(ValueMapping.column_id == column_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_column_and_term(
        self, db: Session, *, column_id: int, nl_term: str
    ) -> Optional[ValueMapping]:
        return (
            db.query(ValueMapping)
            .filter(
                ValueMapping.column_id == column_id, ValueMapping.nl_term == nl_term
            )
            .first()
        )


value_mapping = CRUDValueMapping(ValueMapping)
