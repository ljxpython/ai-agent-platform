from __future__ import annotations

from fastapi import APIRouter

from platform_api.entrypoints.http.system import router as system_router
from platform_api.modules.announcements.presentation import router as announcements_router
from platform_api.modules.agents.presentation import router as assistants_router
from platform_api.modules.audit.presentation import router as audit_router
from platform_api.modules.identity.presentation import router as identity_router
from platform_api.modules.operations.presentation import router as operations_router
from platform_api.modules.projects.presentation import router as projects_router
from platform_api.modules.runtime_catalog.presentation import router as runtime_catalog_router
from platform_api.modules.runtime_gateway.presentation import router as runtime_gateway_router
from platform_api.modules.runtime_policies.presentation import router as runtime_policies_router
from platform_api.modules.service_accounts.presentation import router as service_accounts_router
from platform_api.modules.users.presentation import router as users_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(identity_router)
api_router.include_router(operations_router)
api_router.include_router(projects_router)
api_router.include_router(users_router)
api_router.include_router(service_accounts_router)
api_router.include_router(announcements_router)
api_router.include_router(assistants_router)
api_router.include_router(audit_router)
api_router.include_router(runtime_catalog_router)
api_router.include_router(runtime_policies_router)
api_router.include_router(runtime_gateway_router)
