from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import require_permission, require_role
from app.domains.auth.schemas import CurrentUser
from app.domains.imagenes.schemas import ImagenesHuerfanasResponse, ImagenUploadResponse
from app.domains.imagenes.services import ImagenService
from app.middlewares.limiter import limiter
from app.shared.enums import Action, Module, Role
from app.shared.schemas.errors import error_responses


router = APIRouter(prefix="/imagenes", tags=["Imágenes"])


@router.post(
    "/uploads",
    response_model=ImagenUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir una imagen",
    description=(
        "Imagen de hasta 5 MB, sin SVG. Devuelve su URL, que se envía después en el campo de "
        "imagen de un create o un update. Si ningún registro la usa, queda pendiente y se limpia."
    ),
    responses=error_responses(400, 401, 403, 422, 429, 500),
)
@limiter.limit("30/minute")
async def upload_imagen(
    request: Request,
    file: UploadFile,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.IMAGEN, Action.CREATE))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImagenUploadResponse:
    return await ImagenService.upload(file, settings)


@router.post(
    "/limpiar-huerfanas",
    response_model=ImagenesHuerfanasResponse,
    summary="Borrar las imágenes subidas que nadie usa",
    description=(
        "Lo mismo que hace el cron (jobs/limpiar_imagenes_huerfanas.py), a pedido de un admin: borra "
        "las imágenes pendientes de más de 24 horas que ningún registro usa. Usa la API de "
        "administración de Cloudinary, que tiene un límite de llamadas por hora."
    ),
    responses=error_responses(401, 403, 500),
)
async def limpiar_imagenes_huerfanas(
    # Tarea del sistema (§24): require_role con los roles operativos, no la matriz.
    current_user: Annotated[CurrentUser, Depends(require_role(Role.SUPERADMIN, Role.ADMIN))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImagenesHuerfanasResponse:
    return await ImagenService.limpiar_huerfanas(db_session, settings)
