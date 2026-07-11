"""
Alembic Environment Configuration
Reads DATABASE_URL from environment and applies migrations to Kavach's DB schema.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ─── Path Setup ───────────────────────────────────────────────────────────────
# Ensure project root is on sys.path so db.models can be imported
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

# ─── Import Base + Models ─────────────────────────────────────────────────────
from db.database import Base, DATABASE_URL  # noqa: E402
import db.models  # noqa: F401 — registers all ORM models with Base.metadata

# ─── Alembic Config ───────────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from environment (takes priority over alembic.ini)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Attach Python logging to Alembic
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ─── Offline Migrations ───────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Generate SQL without connecting to the database."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ─── Online Migrations ────────────────────────────────────────────────────────

def run_migrations_online() -> None:
    """Apply migrations using an active database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
