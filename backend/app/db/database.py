# app/db/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# --- CRITICAL: Ensure the engine uses the DATABASE_URL from settings ---
# Log the URL being used for debugging
logger.info(f"Initializing database engine with URL: {settings.DATABASE_URL}")

if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in settings. Check your .env file.")

engine = create_engine(
    settings.DATABASE_URL, # This MUST be the URL from settings
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- FIX 2: Define Base ONCE here ---
Base = declarative_base()

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
