"""
Alembic environment configuration for Mumbai Geo-AI database
Handles migrations for PostgreSQL + PostGIS with spatial indexes
"""

import asyncio
import logging
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
# Import your models
from app.models.models import Base
from app.core.config import settings

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger('alembic.env')

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

# Override sqlalchemy.url with our settings
config.set_main_option(
    "sqlalchemy.url",
    f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    This configures the context with just a URL and not an Engine.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Enable PostGIS support
        render_as_batch=False,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    """
    Run migrations with database connection
    """
    # Enable PostGIS extension if not exists
    try:
        connection.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        connection.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
        logger.info("PostGIS extensions enabled")
    except Exception as e:
        logger.warning(f"Could not enable PostGIS extensions: {e}")

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # PostGIS configuration
        render_as_batch=False,
        compare_type=True,
        compare_server_default=True,
        # Include spatial indexes in autogenerate
        include_object=include_object,
        # Custom rendering for spatial types
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()

def include_object(object, name, type_, reflected, compare_to):
    """
    Filter what objects to include in migrations
    """
    # Include spatial indexes
    if type_ == "index" and "gist" in str(object).lower():
        return True
    
    # Skip some system objects
    if type_ == "table" and name in ["spatial_ref_sys", "geography_columns", "geometry_columns"]:
        return False
        
    return True

def render_item(type_, obj, autogen_context):
    """
    Custom rendering for spatial types and indexes
    """
    # Handle GIST indexes for spatial columns
    if type_ == "index" and hasattr(obj, 'kwargs'):
        if 'postgresql_using' in obj.kwargs and obj.kwargs['postgresql_using'] == 'gist':
            return f"op.create_index({obj.name!r}, {obj.table.name!r}, {obj.columns.keys()!r}, postgresql_using='gist')"
    
    # Default rendering
    return False

async def run_async_migrations() -> None:
    """
    Run migrations in async mode
    """
    # Create async engine
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode with async support
    """
    try:
        # Try async first
        asyncio.run(run_async_migrations())
    except Exception as e:
        logger.warning(f"Async migration failed, falling back to sync: {e}")
        
        # Fallback to sync mode
        from sqlalchemy import create_engine
        
        connectable = create_engine(
            config.get_main_option("sqlalchemy.url"),
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()