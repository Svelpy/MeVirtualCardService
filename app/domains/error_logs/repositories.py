from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.error_logs.models import ErrorLog


class ErrorLogRepository:
    @staticmethod
    def add(db_session: AsyncSession, error_log: ErrorLog) -> None:
        """Agrega el error a la sesión; quien la abrió decide el commit."""
        db_session.add(error_log)
