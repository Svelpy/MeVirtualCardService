from collections.abc import Iterable
from datetime import timedelta

from fastapi import UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.config import Settings
from app.domains.imagenes.repositories import ImagenRepository
from app.domains.imagenes.schemas import ImagenesHuerfanasResponse, ImagenUploadResponse
from app.integrations.cloudinary import CloudinaryService
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


# Una imagen recién subida puede tardar en usarse (el formulario sigue abierto):
# solo se considera huérfana después de este tiempo.
ORPHAN_MIN_AGE = timedelta(hours=24)


class ImagenService:
    """
    Ciclo de una imagen:

    1. El cliente la sube con POST /imagenes/uploads y recibe su URL, pendiente.
    2. La envía en el campo de imagen de un create o un update.
    3. El service del dominio la valida con ensure_new_images antes de guardar.
    4. Después del commit, confirm la saca de pendientes y delete_replaced borra
       las que el registro dejó de usar.

    Cada imagen pertenece a un solo campo de un solo registro: por eso borrar la
    reemplazada nunca rompe la imagen de otro.
    """

    @staticmethod
    async def upload(file: UploadFile, settings: Settings) -> ImagenUploadResponse:
        result = await CloudinaryService.upload_pending(file, settings)
        return ImagenUploadResponse(url=result["url"])

    @staticmethod
    async def ensure_new_images(db_session: AsyncSession, new_urls: dict[str, str], settings: Settings) -> None:
        """
        new_urls: campo → URL que el registro todavía no tenía. Responde 422 con
        cada campo cuya imagen no salió de POST /imagenes/uploads, se repite en la
        misma petición o ya pertenece a otro registro.
        """
        errors: dict[str, str] = {}
        seen: set[str] = set()
        for field, url in new_urls.items():
            if not CloudinaryService.is_uploaded_image_url(url, settings):
                errors[field] = "La imagen debe subirse antes con POST /imagenes/uploads."
            elif url in seen:
                errors[field] = "La misma imagen no puede usarse en dos campos."
            seen.add(url)

        in_use = await ImagenRepository.urls_in_use(db_session, [u for f, u in new_urls.items() if f not in errors])
        for field, url in new_urls.items():
            if url in in_use and field not in errors:
                errors[field] = "La imagen ya pertenece a otro registro."

        if errors:
            raise AppException(
                "Los datos enviados no son válidos.",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                ErrorCode.VALIDATION_ERROR,
                details=errors,
            )

    @staticmethod
    async def confirm(urls: Iterable[str], folder: str, settings: Settings) -> None:
        """Después del commit. No interrumpe la operación si Cloudinary falla."""
        await CloudinaryService.confirm_pending_uploads({url: folder for url in urls}, settings)

    @staticmethod
    async def delete_replaced(urls: Iterable[str]) -> None:
        """Después del commit: las imágenes que el registro dejó de usar."""
        for url in urls:
            await CloudinaryService.safe_delete_image(url)

    @staticmethod
    async def limpiar_huerfanas(db_session: AsyncSession, settings: Settings) -> ImagenesHuerfanasResponse:
        """
        Tarea del sistema: borra de Cloudinary las imágenes subidas hace más de
        ORPHAN_MIN_AGE que siguen pendientes y ningún registro usa. Las pendientes
        que sí usa un registro (su confirmación falló) no se borran: solo pierden
        la etiqueta. La ejecuta el cron (jobs/limpiar_imagenes_huerfanas.py) o un
        admin desde POST /imagenes/limpiar-huerfanas.
        """
        pending = await CloudinaryService.list_pending_uploads(settings, utc_now() - ORPHAN_MIN_AGE)
        in_use = await ImagenRepository.urls_in_use(db_session, [image["url"] for image in pending])
        huerfanas = [image["public_id"] for image in pending if image["url"] not in in_use]
        usadas = [image["public_id"] for image in pending if image["url"] in in_use]
        await CloudinaryService.delete_images(huerfanas)
        await CloudinaryService.remove_pending_tag(usadas)
        return ImagenesHuerfanasResponse(eliminadas=len(huerfanas), conservadas=len(usadas))
