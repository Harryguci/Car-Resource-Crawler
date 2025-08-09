from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # App settings
    app_name: str = "ResourceCrawler"
    debug: bool = True
    version: str = "1.0.0"
    
    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Database settings
    database_url: Optional[str] = None
    database_name: str = "resource_crawler"
    
    # PostgreSQL specific settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "root"
    postgres_password: str = "123456"
    postgres_db: str = "resource_crawler"
    postgres_ssl_mode: str = "prefer"
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20
    postgres_pool_timeout: int = 30
    postgres_pool_recycle: int = 3600
    
    # API settings
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Environment
    environment: str = "development"
    
    # External API settings
    external_api_key: Optional[str] = None
    redis_url: Optional[str] = None
    
    # Pexels API settings
    pexels_base_url: Optional[str] = None
    pexels_secret_key: Optional[str] = None
    request_frequency: int = 30
    resource_dir: str = "blob/pexels"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"
    
    @property
    def is_testing(self) -> bool:
        return self.environment.lower() == "testing"
    
    @property
    def postgres_url(self) -> str:
        """Generate PostgreSQL URL from individual components"""
        if self.database_url:
            return self.database_url
        
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}?sslmode={self.postgres_ssl_mode}"

settings = Settings()