from logging.config import fileConfig

from sqlalchemy import create_engine, pool

import app.models  # noqa: F401 -- register all tables
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
target_metadata = Base.metadata


def database_url() -> str:
    # Tests can supply a disposable URL; CLI reads DATABASE_URL/.env.
    return config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        database_url(),
        poolclass=pool.NullPool,
        connect_args={"options": "-c timezone=UTC", "connect_timeout": 5},
    )
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
