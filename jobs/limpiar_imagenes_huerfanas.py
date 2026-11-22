"""
Borra de Cloudinary las imágenes subidas con POST /imagenes/uploads que nadie
usó: siguen con la etiqueta de pendiente más de 24 horas y ningún registro guarda
su URL.

Es una tarea del sistema (AGENTS.md §24): la ejecuta el cron de la plataforma
con la misma imagen y las mismas variables de entorno que la API:

    python -m jobs.limpiar_imagenes_huerfanas

Frecuencia recomendada: una vez al día (0 4 * * *). Usa la API de
administración de Cloudinary, que tiene un límite de llamadas por hora.

Solo toca las imágenes de este entorno (la carpeta de CLOUDINARY_FOLDER_NAME):
la cuenta y la etiqueta se comparten entre entornos. Una imagen pendiente que sí
usa un registro (su confirmación falló) no se borra: solo pierde la etiqueta.
Si falla, termina con un código distinto de cero para que la plataforma lo marque.
"""

import asyncio

from app.core.config import get_settings
from app.core.database import close_database, initialize_database
from app.core.logging import get_logger, setup_logging
from app.domains.imagenes.schemas import ImagenesHuerfanasResponse
from app.domains.imagenes.services import ImagenService
from app.integrations.cloudinary import configure_cloudinary


logger = get_logger(__name__)


async def main() -> ImagenesHuerfanasResponse:
    settings = get_settings()
    setup_logging(settings)
    # Fuera de la API no hay lifespan que configure el SDK.
    configure_cloudinary(settings)
    engine, session_factory = initialize_database(settings)
    try:
        async with session_factory() as db_session:
            result = await ImagenService.limpiar_huerfanas(db_session, settings)
    finally:
        await close_database(engine)
    logger.info("Imágenes huérfanas eliminadas: %s; pendientes en uso conservadas: %s", result.eliminadas, result.conservadas)
    return result


if __name__ == "__main__":
    asyncio.run(main())
