from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Importar el repository de tarjeta carga los models que necesitan sus Relationship().
import app.domains.tarjeta.repositories  # noqa: F401
from app.domains.pago.models import Pago
from app.domains.tarjeta.models import Tarjeta
from app.domains.tarjeta_seo.models import TarjetaSeo
from app.domains.vitrina_item_imagen.models import VitrinaItemImagen


# Toda columna que guarda una URL de POST /imagenes/uploads. Una columna nueva
# de imagen se agrega aquí.
IMAGE_COLUMNS = (
    Tarjeta.profile_url,
    Tarjeta.photo_usuario_url,
    Tarjeta.logo_empresa_url,
    Tarjeta.cover_url,
    Tarjeta.qr_pago_url,
    TarjetaSeo.og_image_url,
    Pago.comprobante_url,
    VitrinaItemImagen.url,
)


class ImagenRepository:
    """Dominio sin model: consulta las columnas de imagen de los demás."""

    @staticmethod
    async def urls_in_use(db_session: AsyncSession, urls: Collection[str]) -> set[str]:
        """
        Las URLs que ya guarda algún registro, eliminado o no: integridad, sin
        alcance (§24). Un registro eliminado conserva su imagen hasta que se limpie.
        """
        if not urls:
            return set()
        in_use: set[str] = set()
        for column in IMAGE_COLUMNS:
            result = await db_session.execute(select(column).where(column.in_(urls)).distinct())
            in_use.update(result.scalars().all())
        return in_use
