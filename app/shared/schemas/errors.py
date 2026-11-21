from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Formato común de error que consume el frontend."""

    status: Literal["fail", "error"]
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "fail",
                "code": "ERROR_CODE",
                "message": "La solicitud no pudo procesarse.",
                "details": {},
            }
        }
    )


ERROR_RESPONSES: dict[int, dict[str, object]] = {
    400: {"model": ErrorResponse, "description": "Solicitud inválida."},
    401: {"model": ErrorResponse, "description": "No autenticado."},
    403: {"model": ErrorResponse, "description": "Sin permiso para esta acción."},
    404: {"model": ErrorResponse, "description": "Recurso no encontrado."},
    409: {"model": ErrorResponse, "description": "Conflicto con el estado actual del recurso."},
    422: {"model": ErrorResponse, "description": "Datos de entrada inválidos."},
    429: {"model": ErrorResponse, "description": "Demasiadas solicitudes."},
    500: {"model": ErrorResponse, "description": "Error interno del servidor."},
}


def error_responses(*status_codes: int) -> dict[int, dict[str, object]]:
    """Documenta en OpenAPI las respuestas de error de un endpoint."""
    return {status_code: ERROR_RESPONSES[status_code] for status_code in status_codes}
