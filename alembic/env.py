"""Alembic migration environment, wired to the app's SQLAlchemy metadata.

Uses `DATABASE_URL` from the environment so migrations run against the same database the app
does, and `Base.metadata` as the autogenerate target:

    alembic revision --autogenerate -m "describe change"
    alembic upgrade head
"""
from __future__ import annotations

import os

from sqlalchemy import engine_from_config, pool

from alembic import context
from src.db.models import Base

config = context.config

_db_url = os.environ.get("DATABASE_URL", "sqlite:///./socialmedia.db")
config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=_db_url.startswith("sqlite"),
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_db_url.startswith("sqlite"),
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
