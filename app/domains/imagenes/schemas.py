from pydantic import ConfigDict

from app.shared.schemas.base import SchemaBase


class ImagenUploadResponse(SchemaBase):
    """
    URL de una imagen subida y todavía pendiente. Se envía en el campo de imagen
    de un create o un update; si ningún registro la usa, la limpieza de
    Cloudinary la elimina.
    """

    url: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"url": "https://res.cloudinary.com/demo/image/upload/v1700000000/proyecto/imagenes/abc123.jpg"}
        }
    )


class ImagenesHuerfanasResponse(SchemaBase):
    """
    Resultado de la limpieza de imágenes pendientes: eliminadas = huérfanas que
    se borraron de Cloudinary; conservadas = pendientes que sí usa un registro
    (su confirmación había fallado) y que solo perdieron la etiqueta.
    """

    eliminadas: int
    conservadas: int

    model_config = ConfigDict(json_schema_extra={"example": {"eliminadas": 12, "conservadas": 1}})
