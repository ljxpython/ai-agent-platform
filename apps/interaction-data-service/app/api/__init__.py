from __future__ import annotations

from fastapi import APIRouter

from .routes import router as routes_router
from .usecases import router as usecases_router
from .workflows import router as workflows_router

# Keep package-level router assembly consistent with platform-api.
router = APIRouter()
router.include_router(routes_router)
router.include_router(workflows_router)
router.include_router(usecases_router)
