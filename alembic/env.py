from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the project root to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# target_metadata = Base.metadata  <-- Handled inside functions instead


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Deferred to avoid circular import at alembic module load time
    # app imports are safe inside function scope after sys.path is configured
    from app.core.config import settings
    from app.db.session import Base
    from app.models import user, ticket, feedback  # noqa: F401
    
    # Prefer application DB URL over static alembic.ini value
    db_url = settings.DATABASE_URL or config.get_main_option("sqlalchemy.url")
    if not db_url:
        raise ValueError("DATABASE_URL is not set in settings or alembic.ini")
        
    context.configure(
        url=db_url,
        target_metadata=Base.metadata,
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
    # Deferred to avoid circular import at alembic module load time
    from app.core.config import settings
    from app.db.session import Base
    from app.models import user, ticket, feedback  # noqa: F401
    
    # Prefer application DB URL over static alembic.ini value
    configuration = config.get_section(config.config_ini_section) or {}
    db_url = settings.DATABASE_URL or config.get_main_option("sqlalchemy.url")
    if not db_url:
        raise ValueError("DATABASE_URL is not set in settings or alembic.ini")
    configuration["sqlalchemy.url"] = db_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=Base.metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
