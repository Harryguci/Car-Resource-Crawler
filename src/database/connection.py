from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from src.config.settings import settings
import logging
import os

logger = logging.getLogger(__name__)

# Get database URL from environment or settings
DATABASE_URL = os.getenv("DATABASE_URL") or settings.postgres_url

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Ensure we're using the synchronous driver
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_size=settings.postgres_pool_size,
    max_overflow=settings.postgres_max_overflow,
    pool_timeout=settings.postgres_pool_timeout,
    pool_recycle=settings.postgres_pool_recycle,
    pool_pre_ping=True,
)

# Create session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# Create base class for models
Base = declarative_base()

def get_db_session():
    """Get database session"""
    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()

def init_db():
    """Initialize database tables"""
    try:
        # Import all models here to ensure they are registered
        from src.models.image_resource import ImageResourceModel
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

def close_db():
    """Close database connections"""
    engine.dispose()
    logger.info("Database connections closed")
