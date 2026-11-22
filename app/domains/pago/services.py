from datetime import timedelta
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.config import Settings
from app.domains.auth.schemas import CurrentUser
from app.domains.imagenes.services import ImagenService
from app.domains.pago.models import Pago
from app.domains.pago.repositories import PagoRepository
from app.domains.pago.schemas import PagoCreate, PagoResponseItemList
from app.domains.plan.repositories import PlanRepository
from app.domains.plan.services import PLAN_FREE_CODIGO, PlanService
from app.domains.usuario.repositories import UsuarioRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


def _invalid(field: str, message: str) -> AppException:
    return AppException(
        "Los datos enviados no son válidos.",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorCode.VALIDATION_ERROR,
        details={field: message},
    )


class PagoService:
    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int,
        per_page: int,
        user_id: UUID | None = None,
        plan_id: UUID | None = None,
    ) -> PaginatedResponse[PagoResponseItemList]:
        pagos, total = await PagoRepository.list(
            db_session, page=page, per_page=per_page, user_id=user_id, plan_id=plan_id
        )
        return PaginatedResponse[PagoResponseItemList].build(pagos, total=total, page=page, per_page=per_page)

    @staticmethod
    async def get(db_session: AsyncSession, pago_id: UUID) -> Pago:
        pago = await PagoRepository.get(db_session, pago_id, detail=True)
        if pago is None:
            raise AppException("Pago no encontrado.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return pago

    @staticmethod
    async def registrar(db_session: AsyncSession, data: PagoCreate, actor: CurrentUser, settings: Settings) -> Pago:
        """
        Inserta el pago y renueva el plan del usuario: el periodo empieza en su
        vencimiento actual si sigue vigente, o ahora si ya venció.
        """
        # Bloquea al usuario hasta el commit: dos pagos simultáneos no calculan
        # sobre el mismo vencimiento (§19).
        usuario = await UsuarioRepository.get(db_session, data.user_id, for_update=True)
        if usuario is None:
            raise _invalid("user_id", "El usuario no existe.")

        # Idempotencia: un reintento con la misma clave devuelve el pago ya registrado.
        existing = await PagoRepository.get_by_idempotency_key(db_session, data.idempotency_key)
        if existing is not None:
            if existing.user_id == data.user_id and existing.plan_id == data.plan_id:
                return await PagoService.get(db_session, existing.id)
            raise AppException(
                "La clave de idempotencia ya se usó para otro pago.",
                status.HTTP_409_CONFLICT,
                ErrorCode.CONFLICT,
                details={"idempotency_key": "Ya se usó."},
            )

        plan = await PlanRepository.get(db_session, data.plan_id)
        if plan is None:
            raise _invalid("plan_id", "El plan no existe.")
        if plan.codigo == PLAN_FREE_CODIGO:
            raise _invalid("plan_id", "El plan free no se paga.")
        monto = plan.precio if data.monto is None else data.monto
        if monto > plan.precio:
            raise _invalid("monto", f"No puede superar el precio del plan ({plan.precio} {plan.moneda}).")
        if data.comprobante_url is not None:
            await ImagenService.ensure_new_images(db_session, {"comprobante_url": data.comprobante_url}, settings)

        now = utc_now()
        periodo_inicio = max(now, usuario.plan_vence_at)
        periodo_fin = periodo_inicio + timedelta(days=plan.duracion_dias)
        pago = Pago(
            **data.model_dump(exclude={"monto"}),
            monto=monto,
            moneda=plan.moneda,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            created_at=now,
            updated_at=now,
            created_by=actor.id,
        )
        db_session.add(pago)
        usuario.plan_id = plan.id
        usuario.plan_vence_at = periodo_fin
        usuario.updated_at = now
        usuario.updated_by = actor.id
        await db_session.commit()
        if pago.comprobante_url is not None:
            await ImagenService.confirm([pago.comprobante_url], f"pagos/{pago.user_id}", settings)
        return await PagoService.get(db_session, pago.id)

    @staticmethod
    async def anular(db_session: AsyncSession, pago_id: UUID, actor: CurrentUser) -> Pago:
        """
        Inserta el reverso (monto con el signo contrario) y descuenta del
        vencimiento los días que había sumado el pago. El plan pasa a ser el del
        último pago vigente, o free si no queda ninguno. Responde el reverso.
        """
        original = await PagoRepository.get(db_session, pago_id)
        if original is None:
            raise AppException("Pago no encontrado.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        if original.reverses_id is not None:
            raise AppException("Un reverso no se puede anular.", status.HTTP_409_CONFLICT, ErrorCode.CONFLICT)

        usuario = await UsuarioRepository.get(db_session, original.user_id, include_deleted=True, for_update=True)
        # Después del bloqueo: dos anulaciones simultáneas no pasan las dos.
        if await PagoRepository.is_reversed(db_session, original.id):
            raise AppException("El pago ya está anulado.", status.HTTP_409_CONFLICT, ErrorCode.CONFLICT)

        now = utc_now()
        reverso = Pago(
            user_id=original.user_id,
            plan_id=original.plan_id,
            monto=-original.monto,
            moneda=original.moneda,
            metodo=original.metodo,
            periodo_inicio=original.periodo_inicio,
            periodo_fin=original.periodo_fin,
            reverses_id=original.id,
            idempotency_key=f"reverso:{original.id}",
            created_at=now,
            updated_at=now,
            created_by=actor.id,
        )
        db_session.add(reverso)
        await db_session.flush()  # el reverso cuenta al buscar el último pago vigente

        ultimo = await PagoRepository.latest_effective_for_user(db_session, usuario.id)
        usuario.plan_id = ultimo.plan_id if ultimo else (await PlanService.get_free(db_session)).id
        usuario.plan_vence_at = usuario.plan_vence_at - (original.periodo_fin - original.periodo_inicio)
        usuario.updated_at = now
        usuario.updated_by = actor.id
        await db_session.commit()
        return await PagoService.get(db_session, reverso.id)
