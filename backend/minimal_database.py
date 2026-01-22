# minimal_database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from minimal_models import Base  # Import the Base defined in minimal_models.py
from app.core.config import settings  # Use your existing config

# Configure the engine with the database URL from your settings
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define the Base here so models can be registered with it
Base.metadata.create_all(bind=engine)  # This creates tables when the module is imported