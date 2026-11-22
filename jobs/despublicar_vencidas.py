"""
Despublica las tarjetas cuyo dueño tiene el plan vencido.

Es una tarea del sistema: no se expone como endpoint (AGENTS.md §24), la
ejecuta el cron de la plataforma con la misma imagen y las mismas variables de
entorno que la API:

    python -m jobs.despublicar_vencidas

Frecuencia recomendada: cada hora (0 * * * *). La lectura pública ya oculta una
tarjeta en el instante en que vence su plan; este job deja además is_public en
false, para que el dueño y el admin la vean despublicada. Al renovar el plan,
la tarjeta sigue despublicada hasta que su dueño la vuelva a publicar.

Se puede repetir sin efectos: una tarjeta ya despublicada no se toca. Si falla,
termina con un código distinto de cero para que la plataforma lo marque.
"""

import asyncio

from app.core.config import get_settings
from app.core.database import close_database, initialize_database
from app.core.logging import get_logger, setup_logging
from app.domains.tarjeta.services import TarjetaService


logger = get_logger(__name__)


async def main() -> int:
    settings = get_settings()
    setup_logging(settings)
    engine, session_factory = initialize_database(settings)
    try:
        async with session_factory() as db_session:
            count = await TarjetaService.despublicar_vencidas(db_session)
    finally:
        await close_database(engine)
    logger.info("Tarjetas despublicadas por plan vencido: %s", count)
    return count


if __name__ == "__main__":
    asyncio.run(main())
