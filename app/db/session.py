"""
Database session management for Mumbai Geo-AI system
Handles PostgreSQL + PostGIS connection with async support
"""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
import logging

from app.core.config import settings
from app.models.database import Base

logger = logging.getLogger(__name__)

# ================================
# SYNC DATABASE ENGINE
# ================================

# PostgreSQL connection URL
DATABASE_URL = (
    f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

# Async PostgreSQL connection URL  
ASYNC_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

# Synchronous engine (for migrations, bulk operations)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
)

# Asynchronous engine (for FastAPI endpoints)
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)

# Session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
)

# ================================
# SESSION DEPENDENCIES
# ================================

def get_db() -> Generator[Session, None, None]:
    """
    Synchronous database session dependency for FastAPI
    Used in endpoints that need sync database access
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

async def get_async_db() -> AsyncSession:
    """
    Asynchronous database session dependency for FastAPI
    Used in async endpoints (recommended for most API calls)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Async database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

# ================================
# DATABASE INITIALIZATION
# ================================

def init_db() -> None:
    """
    Initialize database tables and PostGIS extension
    Run this during application startup
    """
    try:
        # Enable PostGIS extension
        with engine.connect() as conn:
            # Check if PostGIS is already enabled
            result = conn.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')"
            ).scalar()
            
            if not result:
                logger.info("Enabling PostGIS extension...")
                conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                conn.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
                conn.commit()
            else:
                logger.info("PostGIS extension already enabled")
        
        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialization completed")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def drop_db() -> None:
    """
    Drop all database tables
    WARNING: This will delete all data!
    """
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("Database tables dropped")

async def async_init_db() -> None:
    """
    Async version of database initialization
    """
    try:
        async with async_engine.begin() as conn:
            # Enable PostGIS extension
            result = await conn.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')"
            )
            postgis_exists = result.scalar()
            
            if not postgis_exists:
                logger.info("Enabling PostGIS extension...")
                await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
            
            # Create all tables
            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("Async database initialization completed")
        
    except Exception as e:
        logger.error(f"Async database initialization failed: {e}")
        raise

# ================================
# DATABASE HEALTH CHECK
# ================================

def check_db_connection() -> bool:
    """
    Check if database connection is working
    Returns True if connection is healthy
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

async def async_check_db_connection() -> bool:
    """
    Async version of database health check
    """
    try:
        async with async_engine.begin() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Async database health check failed: {e}")
        return False

# ================================
# UTILITY FUNCTIONS
# ================================

def get_db_info() -> dict:
    """
    Get database connection information for debugging
    """
    return {
        "database_url": DATABASE_URL.replace(f":{settings.POSTGRES_PASSWORD}", ":****"),
        "pool_size": engine.pool.size(),
        "checked_out": engine.pool.checkedout(),
        "overflow": engine.pool.overflow(),
    }

# ================================
# EVENT LISTENERS
# ================================

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Set PostgreSQL connection parameters if needed
    Currently not needed but kept for future configuration
    """
    pass

@event.listens_for(engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """
    Log slow queries for debugging
    """
    if settings.DEBUG:
        context._query_start_time = time.time()

@event.listens_for(engine, "after_cursor_execute")  
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """
    Log query execution time
    """
    if settings.DEBUG:
        total = time.time() - context._query_start_time
        if total > 1.0:  # Log queries taking more than 1 second
            logger.warning(f"Slow query: {total:.2f}s - {statement[:100]}...")

import time  # Import needed for event listeners