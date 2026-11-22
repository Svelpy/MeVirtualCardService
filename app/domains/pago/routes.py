from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.pago.schemas import PagoCreate, PagoResponseAudit, PagoResponseDetail, PagoResponseItemList
from app.domains.pago.services import PagoService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses
from app.shared.schemas.pagination import PaginatedResponse


# Registro (kardex): sin POST /, PATCH ni DELETE. Se inserta con registrar y
# se anula con un reverso (§19).
router = APIRouter(prefix="/pagos", tags=["Pagos"])


@router.get(
    "/",
    response_model=PaginatedResponse[PagoResponseItemList],
    summary="Listar pagos",
    responses=error_responses(401, 403, 422, 500),
)
async def list_pagos(
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PAGO, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    user_id: Annotated[UUID | None, Query()] = None,
    plan_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedResponse[PagoResponseItemList]:
    return await PagoService.list(db_session, page=page, per_page=per_page, user_id=user_id, plan_id=plan_id)


@router.get(
    "/{pago_id}",
    response_model=PagoResponseDetail,
    summary="Obtener un pago",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def get_pago(
    pago_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PAGO, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PagoResponseDetail:
    return await PagoService.get(db_session, pago_id)


@router.get(
    "/{pago_id}/audit",
    response_model=PagoResponseAudit,
    summary="Auditar un pago",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_pago(
    pago_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PAGO, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PagoResponseAudit:
    return await PagoService.get(db_session, pago_id)


@router.post(
    "/registrar",
    response_model=PagoResponseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un pago",
    description=(
        "Renueva el plan del usuario. Sin monto se cobra el precio del plan; con monto (una oferta) "
        "se registra ese importe, que no puede superar el precio. Un reintento con la misma "
        "idempotency_key devuelve el pago ya registrado. comprobante_url es una URL de "
        "POST /imagenes/uploads."
    ),
    responses=error_responses(401, 403, 409, 422, 500),
)
async def registrar_pago(
    data: PagoCreate,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PAGO, Action.CREATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PagoResponseDetail:
    return await PagoService.registrar(db_session, data, current_user, settings)


@router.post(
    "/{pago_id}/anular",
    response_model=PagoResponseDetail,
    summary="Anular un pago",
    description="Inserta un reverso y descuenta del plan del usuario los días que había sumado. Responde el reverso.",
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
async def anular_pago(
    pago_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PAGO, Action.DELETE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PagoResponseDetail:
    return await PagoService.anular(db_session, pago_id, current_user)
