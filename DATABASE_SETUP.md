# Database Setup Guide

This guide will help you set up PostgreSQL database for the ResourceCrawler application.

## Prerequisites

1. **PostgreSQL Server**: Make sure you have PostgreSQL installed and running
2. **Python Dependencies**: Install the required Python packages

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. PostgreSQL Setup

#### Option A: Using Docker (Recommended)

```bash
# Start PostgreSQL container
docker run --name resource-crawler-db \
  -e POSTGRES_DB=resource_crawler \
  -e POSTGRES_USER=root \
  -e POSTGRES_PASSWORD=123456 \
  -p 5432:5432 \
  -d postgres:15

# Or use the provided docker-compose
docker-compose up -d db
```

#### Option B: Local PostgreSQL Installation

1. Install PostgreSQL on your system
2. Create a database and user:

```sql
CREATE DATABASE resource_crawler;
CREATE USER root WITH PASSWORD '123456';
GRANT ALL PRIVILEGES ON DATABASE resource_crawler TO root;
```

### 3. Environment Configuration

Copy the example environment file and configure it:

```bash
cp env.example .env
```

Update the `.env` file with your database settings:

```env
# Database settings
DATABASE_URL=postgresql+asyncpg://root:123456@localhost:5432/resource_crawler?sslmode=prefer
DATABASE_NAME=resource_crawler

# PostgreSQL specific settings
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=root
POSTGRES_PASSWORD=123456
POSTGRES_DB=resource_crawler
POSTGRES_SSL_MODE=prefer
POSTGRES_POOL_SIZE=10
POSTGRES_MAX_OVERFLOW=20
POSTGRES_POOL_TIMEOUT=30
POSTGRES_POOL_RECYCLE=3600
```

### 4. Database Migration

Initialize and run database migrations:

```bash
# Initialize Alembic (first time only)
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Run migrations
alembic upgrade head
```

### 5. Verify Setup

Start the application:

```bash
python run.py
```

Check the health endpoint:

```bash
curl http://localhost:8000/health
```

## Database Schema

The application includes the following main table:

### `image_resources`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| url | VARCHAR | Image URL (unique) |
| filename | VARCHAR | Local filename |
| file_path | VARCHAR | Local file path |
| file_size | INTEGER | File size in bytes |
| width | INTEGER | Image width |
| height | INTEGER | Image height |
| format | VARCHAR | Image format (jpg, png, etc.) |
| source | VARCHAR | Source (pexels, unsplash, etc.) |
| search_query | VARCHAR | Search query used |
| tags | TEXT | JSON array of tags |
| description | TEXT | Image description |
| photographer | VARCHAR | Photographer name |
| photographer_url | VARCHAR | Photographer URL |
| is_downloaded | BOOLEAN | Download status |
| download_status | VARCHAR | Status (pending, downloading, completed, failed) |
| error_message | TEXT | Error message if failed |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

## API Endpoints

### Image Resources

- `GET /api/v1/image-resources/` - List image resources with pagination and filters
- `GET /api/v1/image-resources/{id}` - Get specific image resource
- `POST /api/v1/image-resources/` - Create new image resource
- `PUT /api/v1/image-resources/{id}` - Update image resource
- `DELETE /api/v1/image-resources/{id}` - Delete image resource
- `POST /api/v1/image-resources/bulk` - Bulk create image resources
- `PATCH /api/v1/image-resources/{id}/download-status` - Update download status
- `GET /api/v1/image-resources/statistics` - Get statistics
- `GET /api/v1/image-resources/check-url/{url}` - Check if URL exists

### Query Parameters

- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)
- `search_query`: Search in description, tags, or search_query
- `source`: Filter by source
- `download_status`: Filter by download status
- `is_downloaded`: Filter by download status (boolean)

## Troubleshooting

### Common Issues

1. **Connection Refused**: Make sure PostgreSQL is running and accessible
2. **Authentication Failed**: Check username/password in `.env` file
3. **Database Not Found**: Create the database or check database name
4. **Migration Errors**: Run `alembic upgrade head` to apply pending migrations

### Useful Commands

```bash
# Check database connection
python -c "from src.database.connection import engine; print('Connected!')"

# Reset database
alembic downgrade base
alembic upgrade head

# View migration history
alembic history

# Check current migration
alembic current
```

## Development

### Adding New Models

1. Create the model in `src/models/`
2. Import it in `src/database/connection.py`
3. Generate migration: `alembic revision --autogenerate -m "Add new model"`
4. Apply migration: `alembic upgrade head`

### Database Backup

```bash
# Backup
pg_dump -h localhost -U root -d resource_crawler > backup.sql

# Restore
psql -h localhost -U root -d resource_crawler < backup.sql
```
