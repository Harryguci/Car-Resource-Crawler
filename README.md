# ResourceCrawler

A FastAPI-based application for crawling and managing image resources from various sources like Pexels, with PostgreSQL database integration.

## Features

- **Image Resource Management**: Store and manage image metadata with comprehensive tracking
- **Background Crawling**: Asynchronous image crawling from Pexels API
- **PostgreSQL Database**: Robust data storage with SQLAlchemy ORM
- **RESTful API**: Complete CRUD operations for image resources
- **Search & Filtering**: Advanced search capabilities with pagination
- **Download Tracking**: Monitor download status and progress
- **Statistics**: Comprehensive analytics and reporting

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Docker (optional, for database)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ResourceCrawler
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL**
   
   **Option A: Using Docker (Recommended)**
   ```bash
   docker-compose up -d db
   ```
   
   **Option B: Local PostgreSQL**
   ```sql
   CREATE DATABASE resource_crawler;
   CREATE USER root WITH PASSWORD '123456';
   GRANT ALL PRIVILEGES ON DATABASE resource_crawler TO root;
   ```

4. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your database settings
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the application**
   ```bash
   python run.py
   ```

7. **Test the setup**
   ```bash
   python test_db_connection.py
   ```

## API Endpoints

### Image Resources

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/image-resources/` | List image resources with pagination |
| GET | `/api/v1/image-resources/{id}` | Get specific image resource |
| POST | `/api/v1/image-resources/` | Create new image resource |
| PUT | `/api/v1/image-resources/{id}` | Update image resource |
| DELETE | `/api/v1/image-resources/{id}` | Delete image resource |
| POST | `/api/v1/image-resources/bulk` | Bulk create image resources |
| PATCH | `/api/v1/image-resources/{id}/download-status` | Update download status |
| GET | `/api/v1/image-resources/statistics` | Get statistics |
| GET | `/api/v1/image-resources/check-url/{url}` | Check if URL exists |

### Crawler Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/crawler/start` | Start image crawler |
| GET | `/api/v1/crawler/status` | Get crawler status |
| POST | `/api/v1/crawler/stop` | Stop crawler |
| GET | `/api/v1/crawler/test` | Test API connection |
| GET | `/api/v1/crawler/config` | Get crawler configuration |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Application info |
| GET | `/health` | Health check |
| GET | `/config` | Configuration info |

## Database Schema

### Image Resources Table

The `image_resources` table stores comprehensive metadata about images:

- **Basic Info**: URL, filename, file path, size, dimensions
- **Source Info**: Source platform, search query, photographer details
- **Metadata**: Tags, description, format
- **Status**: Download status, error messages
- **Timestamps**: Creation and update times

## Configuration

### Environment Variables

Key configuration options in `.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=root
POSTGRES_PASSWORD=123456
POSTGRES_DB=resource_crawler

# API
PEXELS_SECRET_KEY=your_pexels_api_key
REQUEST_FREQUENCY=30

# Application
DEBUG=true
LOG_LEVEL=INFO
```

## Development

### Project Structure

```
ResourceCrawler/
├── src/
│   ├── config/          # Configuration settings
│   ├── database/        # Database connection and models
│   ├── models/          # Pydantic schemas and SQLAlchemy models
│   ├── routes/          # API route handlers
│   ├── services/        # Business logic layer
│   ├── utils/           # Utility functions
│   └── backgroundworker/ # Background tasks
├── alembic/             # Database migrations
├── docker/              # Docker configuration
├── blob/                # Downloaded images
└── docs/                # Documentation
```

### Adding New Models

1. Create the model in `src/models/`
2. Import it in `src/database/connection.py`
3. Generate migration: `alembic revision --autogenerate -m "Add new model"`
4. Apply migration: `alembic upgrade head`

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history
```

## Testing

### Database Connection Test

```bash
python test_db_connection.py
```

### API Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test image resources endpoint
curl http://localhost:8000/api/v1/image-resources/

# Test crawler endpoint
curl http://localhost:8000/api/v1/crawler/test
```

## Docker

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Manual Docker Setup

```bash
# Start PostgreSQL
docker run --name resource-crawler-db \
  -e POSTGRES_DB=resource_crawler \
  -e POSTGRES_USER=root \
  -e POSTGRES_PASSWORD=123456 \
  -p 5432:5432 \
  -d postgres:15
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check PostgreSQL is running
   - Verify connection settings in `.env`
   - Run `python test_db_connection.py`

2. **Migration Errors**
   - Run `alembic upgrade head`
   - Check database permissions
   - Verify database exists

3. **API Key Issues**
   - Set `PEXELS_SECRET_KEY` in `.env`
   - Test with `/api/v1/crawler/test` endpoint

### Logs

Check application logs for detailed error information:

```bash
# View application logs
tail -f logs/app.log

# Check database logs (Docker)
docker-compose logs db
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Check the [DATABASE_SETUP.md](DATABASE_SETUP.md) for detailed database setup
- Review the [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for configuration options
- Open an issue on GitHub
