# Environment Variables in FastAPI

This guide explains how to use environment variables in your FastAPI application.

## Overview

The project uses `pydantic_settings` to manage environment variables with type validation, default values, and automatic loading from `.env` files.

## Setup

### 1. Create a `.env` file

Copy the example file and customize it for your environment:

```bash
cp env.example .env
```

### 2. Configure your environment variables

Edit the `.env` file with your actual values:

```env
# App settings
APP_NAME=ResourceCrawler
DEBUG=true
VERSION=1.0.0

# Server settings
HOST=127.0.0.1
PORT=8000

# Database settings
DATABASE_URL=postgresql://user:password@localhost:5432/resource_crawler
DATABASE_NAME=resource_crawler

# Security settings
SECRET_KEY=your-super-secret-key-change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# External services
REDIS_URL=redis://localhost:6379
EXTERNAL_API_KEY=your-external-api-key
EXTERNAL_API_URL=https://api.external-service.com

# Environment
ENVIRONMENT=development
```

## How to Use Environment Variables

### 1. In Settings (`src/config/settings.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "ResourceCrawler"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### 2. In Main Application (`src/main.py`)

```python
from src.config.settings import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug
)
```

### 3. In Routes (`src/routes/items.py`)

```python
from src.config.settings import settings

@router.get("/items/")
def get_items():
    if settings.debug:
        print(f"Debug: Retrieved {len(items_db)} items")
    
    if settings.is_production:
        # Production-specific logic
        pass
    
    return items_db
```

### 4. Using Utility Functions (`src/utils/env_utils.py`)

```python
from src.utils.env_utils import get_environment_info, validate_required_env_vars

# Get environment information
env_info = get_environment_info()

# Validate required variables
validation = validate_required_env_vars()
```

## Environment Variable Priority

1. **System environment variables** (highest priority)
2. **`.env` file** (loaded automatically)
3. **Default values** (lowest priority)

## Available Environment Variables

### App Settings
- `APP_NAME`: Application name
- `DEBUG`: Enable debug mode (true/false)
- `VERSION`: Application version

### Server Settings
- `HOST`: Server host address
- `PORT`: Server port number

### Database Settings
- `DATABASE_URL`: Database connection string
- `DATABASE_NAME`: Database name

### API Settings
- `API_PREFIX`: API route prefix
- `CORS_ORIGINS`: Allowed CORS origins (JSON array)

### Security Settings
- `SECRET_KEY`: Secret key for JWT tokens
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time

### External Services
- `REDIS_URL`: Redis connection URL
- `EXTERNAL_API_KEY`: External API key
- `EXTERNAL_API_URL`: External API base URL

### Logging
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `LOG_FILE`: Log file path

### Environment
- `ENVIRONMENT`: Environment name (development, production, testing)

## Running the Application

### Using the startup script

```bash
python run.py
```

### Using uvicorn directly

```bash
uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

### Using environment variables in command line

```bash
DEBUG=true PORT=8080 python run.py
```

## Environment-Specific Behavior

### Development Environment
- Debug mode enabled
- Detailed error messages
- Hot reload enabled
- Verbose logging

### Production Environment
- Debug mode disabled
- Minimal error details
- Performance optimizations
- Structured logging

### Testing Environment
- Test-specific configurations
- Mock external services
- In-memory databases

## Validation and Security

### Required Variables
The application validates that critical environment variables are set:
- `SECRET_KEY`: Must be changed from default
- `DATABASE_URL`: Required for database operations
- `EXTERNAL_API_KEY`: Required for external API calls

### Security Best Practices
1. **Never commit `.env` files** to version control
2. **Use strong secret keys** in production
3. **Limit CORS origins** to trusted domains
4. **Use environment-specific configurations**
5. **Validate all environment variables** on startup

## API Endpoints for Environment Info

### Get Configuration Status
```http
GET /config
```

### Get Health Check
```http
GET /health
```

### Get Environment Info (Debug Only)
```http
GET /api/v1/items/env/info
```

### Validate Configuration
```http
GET /api/v1/items/config/validation
```

## Troubleshooting

### Common Issues

1. **Environment variables not loading**
   - Check if `.env` file exists in project root
   - Verify file encoding is UTF-8
   - Ensure no spaces around `=` in `.env` file

2. **Type validation errors**
   - Ensure boolean values are `true`/`false` (not `True`/`False`)
   - Check that numeric values don't have quotes
   - Verify JSON arrays are properly formatted

3. **Missing required variables**
   - Use the validation endpoint to check status
   - Review the startup script output for warnings

### Debug Mode
Enable debug mode to get more detailed information:
```env
DEBUG=true
```

This will provide additional logging and expose debug endpoints.
