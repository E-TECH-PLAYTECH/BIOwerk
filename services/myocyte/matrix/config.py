"""Configuration management using Pydantic Settings."""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # PostgreSQL Configuration
    postgres_host: str = Field(default="postgres", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_user: str = Field(default="biowerk", description="PostgreSQL user")
    postgres_password: str = Field(default="biowerk_dev_password", description="PostgreSQL password")
    postgres_db: str = Field(default="biowerk", description="PostgreSQL database name")

    # MongoDB Configuration
    mongo_host: str = Field(default="mongodb", description="MongoDB host")
    mongo_port: int = Field(default=27017, description="MongoDB port")
    mongo_user: str = Field(default="biowerk", description="MongoDB user")
    mongo_password: str = Field(default="biowerk_dev_password", description="MongoDB password")
    mongo_db: str = Field(default="biowerk", description="MongoDB database name")

    # Redis Configuration
    redis_host: str = Field(default="redis", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_db: int = Field(default=0, description="Redis database number")

    # Cache Configuration
    cache_ttl: int = Field(default=300, description="Default cache TTL in seconds")
    cache_enabled: bool = Field(default=True, description="Enable caching")

    # Application Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment (development, staging, production)")

    # Authentication Configuration
    jwt_secret_key: str = Field(default="dev-secret-key-change-in-production", description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(default=30, description="Access token expiration in minutes")
    jwt_refresh_token_expire_days: int = Field(default=7, description="Refresh token expiration in days")
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    require_auth: bool = Field(default=False, description="Require authentication for all endpoints")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def postgres_url(self) -> str:
        """Generate PostgreSQL connection URL."""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def postgres_url_sync(self) -> str:
        """Generate synchronous PostgreSQL connection URL for Alembic."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def mongo_url(self) -> str:
        """Generate MongoDB connection URL."""
        if self.mongo_user and self.mongo_password:
            return f"mongodb://{self.mongo_user}:{self.mongo_password}@{self.mongo_host}:{self.mongo_port}/{self.mongo_db}?authSource=admin"
        return f"mongodb://{self.mongo_host}:{self.mongo_port}/{self.mongo_db}"

    @property
    def redis_url(self) -> str:
        """Generate Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


# Global settings instance
settings = Settings()
