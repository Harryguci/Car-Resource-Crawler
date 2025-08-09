from src.config.settings import settings
import os
from typing import Any, Dict

def get_environment_info() -> Dict[str, Any]:
    """Get information about the current environment"""
    return {
        "environment": settings.environment,
        "is_development": settings.is_development,
        "is_production": settings.is_production,
        "is_testing": settings.is_testing,
        "debug_mode": settings.debug
    }

def get_database_config() -> Dict[str, Any]:
    """Get database configuration from environment variables"""
    return {
        "database_url": settings.database_url,
        "database_name": settings.database_name,
        "is_configured": settings.database_url is not None
    }

def get_api_config() -> Dict[str, Any]:
    """Get API configuration from environment variables"""
    return {
        "api_prefix": settings.api_prefix,
        "cors_origins": settings.cors_origins,
        "access_token_expire_minutes": settings.access_token_expire_minutes
    }

def get_external_services_config() -> Dict[str, Any]:
    """Get external services configuration"""
    return {
        "redis_url": settings.redis_url,
        "external_api_key": settings.external_api_key,
        "external_api_url": settings.external_api_url,
        "redis_configured": settings.redis_url is not None,
        "external_api_configured": settings.external_api_key is not None
    }

def validate_required_env_vars() -> Dict[str, bool]:
    """Validate that required environment variables are set"""
    required_vars = {
        "DATABASE_URL": bool(settings.database_url),
    }
    
    return required_vars

def get_logging_config() -> Dict[str, Any]:
    """Get logging configuration from environment variables"""
    return {
        "log_level": settings.log_level,
        "log_file": settings.log_file,
        "environment": settings.environment
    }

def get_pexels_config() -> Dict[str, Any]:
    """Get Pexels configuration from environment variables"""
    return {
        "pexels_base_url": settings.pexels_base_url,
        "pexels_secret_key": settings.pexels_secret_key,
        "request_frequency": settings.request_frequency,
        "resource_dir": settings.resource_dir
    }