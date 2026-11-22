from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.plan.schemas import PlanPublic, PlanResponse, PlanResponseAudit, PlanUpdate
from app.domains.plan.services import PlanService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/planes", tags=["Planes"])


# Antes de /{plan_id}, para que "public" no se lea como un id.
@router.get(
    "/public",
    response_model=list[PlanPublic],
    summary="Listar los planes visibles (página de precios)",
    responses=error_responses(500),
)
async def list_public_planes(db_session: Annotated[AsyncSession, Depends(get_db)]) -> list[PlanPublic]:
    return await PlanService.list_public(db_session)


@router.get(
    "/",
    response_model=PaginatedResponse[PlanResponse],
    summary="Listar planes",
    responses=error_responses(401, 403, 422, 500),
)
async def list_planes(
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PLAN, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    is_visible: Annotated[bool | None, Query()] = None,
) -> PaginatedResponse[PlanResponse]:
    return await PlanService.list(db_session, page=page, per_page=per_page, is_visible=is_visible)


@router.get(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Obtener un plan",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def get_plan(
    plan_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PLAN, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PlanResponse:
    return await PlanService.get(db_session, plan_id)


@router.get(
    "/{plan_id}/audit",
    response_model=PlanResponseAudit,
    summary="Auditar un plan",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_plan(
    plan_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PLAN, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PlanResponseAudit:
    return await PlanService.get(db_session, plan_id, include_deleted=True)


@router.patch(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Editar un plan",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def update_plan(
    plan_id: UUID,
    data: PlanUpdate,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PLAN, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PlanResponse:
    return await PlanService.update(db_session, plan_id, data, current_user)
