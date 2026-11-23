
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, event, pool

# Ensure the backend directory is available for application imports.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import Base
from app import models  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Use the same database URL as the FastAPI application.
config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("%", "%%"),
)


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Enable SQLite foreign-key enforcement on Alembic connections too.
    if settings.database_url.startswith("sqlite"):

        @event.listens_for(connectable, "connect")
        def enable_sqlite_foreign_keys(
            dbapi_connection,
            connection_record,
        ):
            cursor = dbapi_connection.cursor()

            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
