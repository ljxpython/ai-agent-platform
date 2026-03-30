from __future__ import annotations

from fastapi import APIRouter

from .aggregates import router as aggregates_router
from .documents import router as documents_router
from .test_cases import router as test_cases_router


router = APIRouter(prefix="/test-case-service")
router.include_router(aggregates_router)
router.include_router(documents_router)
router.include_router(test_cases_router)
