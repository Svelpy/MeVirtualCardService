from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.tarjeta_theme.models import TarjetaTheme
from app.domains.tarjeta_theme.repositories import TarjetaThemeRepository
from app.domains.tarjeta_theme.schemas import (
    COLOR_FIELDS,
    THEME_PRESETS,
    TarjetaThemeAplicarPreset,
    TarjetaThemeUpdate,
)
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class TarjetaThemeService:
    @staticmethod
    async def get(
        db_session: AsyncSession,
        theme_id: UUID,
        actor: CurrentUser,
        *,
        include_deleted: bool = False,
    ) -> TarjetaTheme:
        theme = await TarjetaThemeRepository.get(
            db_session, theme_id, scope=tarjeta_scope_for(actor), include_deleted=include_deleted
        )
        if theme is None:
            raise AppException("Theme no encontrado.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return theme

    @staticmethod
    async def update(
        db_session: AsyncSession,
        theme_id: UUID,
        data: TarjetaThemeUpdate,
        actor: CurrentUser,
    ) -> TarjetaTheme:
        """Cambiar un color a mano deja el theme como personalizado (preset = NULL)."""
        theme = await TarjetaThemeService.get(db_session, theme_id, actor)
        changes = {
            field: value
            for field, value in data.model_dump(exclude_unset=True).items()
            if getattr(theme, field) != value
        }
        if changes:
            for field, value in changes.items():
                setattr(theme, field, value)
            if set(changes) & set(COLOR_FIELDS):
                theme.preset = None
            theme.updated_at = utc_now()
            theme.updated_by = actor.id
            await db_session.commit()
        return await TarjetaThemeService.get(db_session, theme_id, actor)

    @staticmethod
    async def aplicar_preset(
        db_session: AsyncSession,
        theme_id: UUID,
        data: TarjetaThemeAplicarPreset,
        actor: CurrentUser,
    ) -> TarjetaTheme:
        """Copia los colores del preset. La tipografía y el resto de la apariencia no cambian."""
        theme = await TarjetaThemeService.get(db_session, theme_id, actor)
        for field, value in THEME_PRESETS[data.preset].items():
            setattr(theme, field, value)
        theme.preset = data.preset
        theme.updated_at = utc_now()
        theme.updated_by = actor.id
        await db_session.commit()
        return await TarjetaThemeService.get(db_session, theme_id, actor)
