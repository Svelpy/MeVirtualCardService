from collections.abc import Sequence
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.domains.auth.schemas import CurrentUser
from app.domains.plan.models import Plan
from app.domains.plan.repositories import PlanRepository
from app.domains.plan.schemas import PlanResponse, PlanUpdate
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


# Plan con el que empieza todo usuario nuevo (fila sembrada en la migración inicial).
PLAN_FREE_CODIGO = "free"


class PlanService:
    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int,
        per_page: int,
        is_visible: bool | None = None,
    ) -> PaginatedResponse[PlanResponse]:
        planes, total = await PlanRepository.list(db_session, page=page, per_page=per_page, is_visible=is_visible)
        return PaginatedResponse[PlanResponse].build(planes, total=total, page=page, per_page=per_page)

    @staticmethod
    async def list_public(db_session: AsyncSession) -> Sequence[Plan]:
        return await PlanRepository.list_visible(db_session)

    @staticmethod
    async def get(db_session: AsyncSession, plan_id: UUID, *, include_deleted: bool = False) -> Plan:
        plan = await PlanRepository.get(db_session, plan_id, include_deleted=include_deleted)
        if plan is None:
            raise AppException("Plan no encontrado.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return plan

    @staticmethod
    async def get_free(db_session: AsyncSession) -> Plan:
        plan = await PlanRepository.get_by_codigo(db_session, PLAN_FREE_CODIGO)
        if plan is None:
            # Lo siembra la migración inicial: si falta, la base no está migrada.
            raise RuntimeError(f"No existe el plan '{PLAN_FREE_CODIGO}': falta aplicar la migración inicial.")
        return plan

    @staticmethod
    async def update(db_session: AsyncSession, plan_id: UUID, data: PlanUpdate, actor: CurrentUser) -> Plan:
        plan = await PlanService.get(db_session, plan_id)
        changes = data.model_dump(exclude_unset=True)
        if changes:
            for field, value in changes.items():
                setattr(plan, field, value)
            plan.updated_at = utc_now()
            plan.updated_by = actor.id
            await db_session.commit()
        return await PlanService.get(db_session, plan_id)
