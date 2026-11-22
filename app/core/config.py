from functools import lru_cache
from typing import Literal, Self
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, field_validator, model_validator
Environment = Literal["development","staging","production","test"]

class Settings(BaseSettings):
    """Configuración de la aplicación usando variables de entorno"""
    
    # =================================
    # Application
    # =================================
    APP_NAME: str = "Backend API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "API del backend."
    ENVIRONMENT: Environment = "development"
    # Swagger/ReDoc. Si no se define, sigue a DEBUG (solo en development).
    DOCS_ENABLED: bool | None = None
    # =================================
    # PostgreSQL
    # =================================
    DATABASE_URL: str | None = None
    TEST_DATABASE_URL: str | None = None
    # =================================
    # Seed de los superadmins (python -m seeds.superadmin)
    # =================================
    SEED_SUPERADMIN_1_EMAIL: str | None = None
    SEED_SUPERADMIN_1_PASSWORD: SecretStr | None = None
    SEED_SUPERADMIN_2_EMAIL: str | None = None
    SEED_SUPERADMIN_2_PASSWORD: SecretStr | None = None
    SEED_SUPERADMIN_3_EMAIL: str | None = None
    SEED_SUPERADMIN_3_PASSWORD: SecretStr | None = None
    @property
    def SEED_SUPERADMINS(self) -> list[tuple[str | None, SecretStr | None]]:
        """(email, password) de cada superadmin del seed, en orden."""
        return [
            (self.SEED_SUPERADMIN_1_EMAIL, self.SEED_SUPERADMIN_1_PASSWORD),
            (self.SEED_SUPERADMIN_2_EMAIL, self.SEED_SUPERADMIN_2_PASSWORD),
            (self.SEED_SUPERADMIN_3_EMAIL, self.SEED_SUPERADMIN_3_PASSWORD),
        ]
    # =================================
    # JWT
    # =================================
    SECRET_KEY: str
    CSRF_SECRET_KEY: str
    ALGORITHM: Literal["HS256"] = "HS256"
  # =================================
    # Cloudinary
    # =================================
    CLOUDINARY_CLOUD_NAME: str | None = None
    CLOUDINARY_API_KEY: str | None = None
    CLOUDINARY_API_SECRET: str | None = None
    CLOUDINARY_FOLDER_NAME_PRODUCTION: str | None = None
    TEST_CLOUDINARY_FOLDER_NAME: str | None = None
    @property
    def CLOUDINARY_FOLDER_NAME(self) -> str:
        if self.ENVIRONMENT == "production":
            folder = self.CLOUDINARY_FOLDER_NAME_PRODUCTION
            variable_name = "CLOUDINARY_FOLDER_NAME_PRODUCTION"
        else:
            folder = self.TEST_CLOUDINARY_FOLDER_NAME
            variable_name = "TEST_CLOUDINARY_FOLDER_NAME"

        if not folder:
            raise ValueError(f"Debe configurarse {variable_name} para Cloudinary")
        return folder
    #----------------------------------
    # Resend (correo transaccional)
    #----------------------------------
    RESEND_API_KEY: str | None = None
    RESEND_FROM_EMAIL: str | None = None
    RESEND_REPLY_TO: str | None = None
    AUTH_FRONTEND_URL: str = "http://localhost:5173"
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0)
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = Field(default=48, gt=0)
    # =================================
    # CORS
    # =================================
    DEV_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"
    PROD_ORIGINS: str | None = None
    @property
    def CORS_ORIGINS_LIST(self) -> list[str]:


        if self.ENVIRONMENT in {"development", "test"}:
            origins = self.DEV_ORIGINS
        else:
            origins = self.PROD_ORIGINS
        if not origins:
            raise ValueError("Debe configurarse PROD_ORIGINS en producción")
        # El navegador envía el Origin sin "/" final; se normaliza para que coincida.
        return [
            origin.strip().rstrip("/")
            for origin in origins.split(",")
            if origin.strip().rstrip("/")
        ]

    ACCESS_TOKEN_EXPIRE_MINUTES_DEVELOPMENT: int = Field(default=10, gt=0)
    ACCESS_TOKEN_EXPIRE_MINUTES_STAGING: int = Field(default=15, gt=0)
    ACCESS_TOKEN_EXPIRE_MINUTES_PRODUCTION: int = Field(default=15, gt=0)
    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        durations = {
            "development": self.ACCESS_TOKEN_EXPIRE_MINUTES_DEVELOPMENT,
            "staging": self.ACCESS_TOKEN_EXPIRE_MINUTES_STAGING,
            "production": self.ACCESS_TOKEN_EXPIRE_MINUTES_PRODUCTION,
            "test": self.ACCESS_TOKEN_EXPIRE_MINUTES_DEVELOPMENT,
        }
        return durations[self.ENVIRONMENT]

    REFRESH_TOKEN_EXPIRE_DAYS_DEVELOPMENT: int = Field(default=7, gt=0)
    REFRESH_TOKEN_EXPIRE_DAYS_STAGING: int = Field(default=7, gt=0)
    REFRESH_TOKEN_EXPIRE_DAYS_PRODUCTION: int = Field(default=7, gt=0)
    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        durations = {
            "development": self.REFRESH_TOKEN_EXPIRE_DAYS_DEVELOPMENT,
            "staging": self.REFRESH_TOKEN_EXPIRE_DAYS_STAGING,
            "production": self.REFRESH_TOKEN_EXPIRE_DAYS_PRODUCTION,
            "test": self.REFRESH_TOKEN_EXPIRE_DAYS_DEVELOPMENT,
        }
        return durations[self.ENVIRONMENT]

    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    @property
    def REFRESH_TOKEN_COOKIE_SECURE(self) -> bool:
        return self.ENVIRONMENT in {"staging", "production"}
    
    @property
    def DEBUG(self) -> bool:
        return self.ENVIRONMENT == "development"

    @field_validator("DOCS_ENABLED", mode="before")
    @classmethod
    def validate_docs_enabled(cls, value: object) -> object:
        # Una variable vacía (DOCS_ENABLED=) equivale a no definirla.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def resolve_docs_enabled(self) -> Self:
        if self.DOCS_ENABLED is None:
            self.DOCS_ENABLED = self.DEBUG
        return self

    @model_validator(mode="after")
    def validate_security_settings(self) -> Self:
        if len(self.SECRET_KEY.encode("utf-8")) < 32:
            raise ValueError("SECRET_KEY debe contener al menos 32 bytes.")

        if len(self.CSRF_SECRET_KEY.encode("utf-8")) < 32:
            raise ValueError("CSRF_SECRET_KEY debe contener al menos 32 bytes.")

        if self.SECRET_KEY == self.CSRF_SECRET_KEY:
            raise ValueError("SECRET_KEY y CSRF_SECRET_KEY deben ser diferentes.")

        return self
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
@lru_cache
def get_settings() -> Settings:
    return Settings()

