from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.config import Settings
from app.domains.auth.schemas import CurrentUser
from app.domains.imagenes.services import ImagenService
from app.domains.tarjeta.services import tarjeta_image_folder, tarjeta_scope_for
from app.domains.tarjeta_seo.models import TarjetaSeo
from app.domains.tarjeta_seo.repositories import TarjetaSeoRepository
from app.domains.tarjeta_seo.schemas import TarjetaSeoUpdate
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class TarjetaSeoService:
    @staticmethod
    async def get(
        db_session: AsyncSession,
        seo_id: UUID,
        actor: CurrentUser,
        *,
        include_deleted: bool = False,
    ) -> TarjetaSeo:
        seo = await TarjetaSeoRepository.get(
            db_session, seo_id, scope=tarjeta_scope_for(actor), include_deleted=include_deleted
        )
        if seo is None:
            raise AppException("SEO no encontrado.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return seo

    @staticmethod
    async def update(
        db_session: AsyncSession,
        seo_id: UUID,
        data: TarjetaSeoUpdate,
        actor: CurrentUser,
        settings: Settings,
    ) -> TarjetaSeo:
        seo = await TarjetaSeoService.get(db_session, seo_id, actor)
        changes = {
            field: value
            for field, value in data.model_dump(exclude_unset=True).items()
            if getattr(seo, field) != value
        }
        replaced = []
        if "og_image_url" in changes:
            if changes["og_image_url"] is not None:
                await ImagenService.ensure_new_images(
                    db_session, {"og_image_url": changes["og_image_url"]}, settings
                )
            if seo.og_image_url:
                replaced.append(seo.og_image_url)
        if changes:
            for field, value in changes.items():
                setattr(seo, field, value)
            seo.updated_at = utc_now()
            seo.updated_by = actor.id
            await db_session.commit()
            if changes.get("og_image_url"):
                await ImagenService.confirm([changes["og_image_url"]], tarjeta_image_folder(seo.id), settings)
            await ImagenService.delete_replaced(replaced)
        return await TarjetaSeoService.get(db_session, seo_id, actor)
