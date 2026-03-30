from __future__ import annotations

from fastapi import APIRouter

from .assistants import router as assistants_router
from .audit import router as audit_router
from .auth import router as auth_router
from .catalog import router as catalog_router
from .members import router as members_router
from .projects import router as projects_router
from .runtime_capabilities import router as runtime_capabilities_router
from .runtime_policies import router as runtime_policies_router
from .testcase import router as testcase_router
from .users import router as users_router

router = APIRouter(prefix="/_management", tags=["management"])
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(projects_router)
router.include_router(members_router)
router.include_router(audit_router)
router.include_router(assistants_router)
router.include_router(catalog_router)
router.include_router(runtime_policies_router)
router.include_router(runtime_capabilities_router)
router.include_router(testcase_router)
