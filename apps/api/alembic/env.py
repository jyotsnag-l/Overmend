import os
import sys
import socket
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context

# Add apps/api to path so we can import config and models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
import models

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = models.Base.metadata

def get_db_url() -> str:
    # Allow override from env
    if os.environ.get("ALEMBIC_DB_URL"):
        return os.environ.get("ALEMBIC_DB_URL")

    db_url = settings.SYNC_DATABASE_URL
    
    # Check if PostgreSQL is reachable
    if "postgresql" in db_url:
        try:
            # Extract host and port
            parts = db_url.split("@")
            if len(parts) > 1:
                host_port = parts[1].split("/")[0]
                if ":" in host_port:
                    host, port = host_port.split(":")
                    port = int(port)
                else:
                    host = host_port
                    port = 5432
                
                # Attempt socket connection
                with socket.create_connection((host, port), timeout=1.0):
                    pass
        except Exception:
            # Fallback to local SQLite for migration generation/development
            return "sqlite:///alembic_temp.db"
    
    return db_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    db_url = get_db_url()
    
    # If using sqlite, ensure we configure it appropriately
    if db_url.startswith("sqlite"):
        connectable = create_engine(db_url, poolclass=pool.NullPool)
    else:
        # PostgreSQL configurations
        connectable = create_engine(db_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True if db_url.startswith("sqlite") else False
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
