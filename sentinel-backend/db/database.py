"""
Kavach -- SQLAlchemy Engine, Session Factory & Dynamic Fallback
Supports PostgreSQL (production) or SQLite (fallback for development/testing).

Configure via environment variable:
  DATABASE_URL=postgresql+psycopg://user:password@host:port/dbname

If the PostgreSQL connection fails or port is closed, dynamically falls back to SQLite.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

# ─── Connection URL ───────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://kavach:kavach123@localhost:5432/kavach_db"
)

# ─── Engine Initialization ───────────────────────────────────────────────────

# Attempt Postgres connection first, fallback to SQLite if unreachable
engine = None
try:
    if "sqlite" in DATABASE_URL:
        raise ValueError("Explicitly requested SQLite.")
    
    # Configure production pool settings
    engine = create_engine(
        DATABASE_URL,
        connect_args={"connect_timeout": 2},
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        echo=False,
    )
    # Ping the engine to confirm it's actually alive
    with engine.connect() as conn:
        pass
    print("  [DB] Successfully connected to PostgreSQL production database.")
except Exception as e:
    print(f"  [DB] PostgreSQL connection failed ({e}). Falling back to SQLite local database.")
    # Local SQLite DB fallback for testing and offline execution
    DATABASE_URL = "sqlite:///./kavach.db"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Required for SQLite concurrency
        echo=False,
    )

# ─── Session Factory ──────────────────────────────────────────────────────────

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ─── Declarative Base ─────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass

# ─── FastAPI Dependency ───────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── Generic Bulk UPSERT Helper ────────────────────────────────────────────────

def bulk_upsert(db, model_class, values_list, index_elements):
    """
    Perform a high-performance bulk upsert (INSERT ... ON CONFLICT DO UPDATE).
    Detects the current database dialect and executes dialect-specific upsert statement.
    
    - index_elements: List of columns that form the unique key/constraint (e.g. ['borrower_id', 'month_index']).
    """
    if not values_list:
        return 0

    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        insert_fn = pg_insert
    elif dialect == "sqlite":
        insert_fn = sqlite_insert
    else:
        # Fallback to slower session.merge for unsupported dialects
        for val in values_list:
            db.merge(model_class(**val))
        db.commit()
        return len(values_list)

    # Get non-unique and non-primary key columns to update on conflict
    all_columns = [c.name for c in model_class.__table__.columns]
    pk_columns = [c.name for c in model_class.__table__.columns if c.primary_key]
    update_cols = {
        col: getattr(insert_fn(model_class).excluded, col)
        for col in all_columns
        if col not in index_elements and col not in pk_columns
    }

    # Batch updates in sizes of 500
    BATCH_SIZE = 500
    total_upserted = 0
    for i in range(0, len(values_list), BATCH_SIZE):
        batch = values_list[i : i + BATCH_SIZE]
        stmt = insert_fn(model_class).values(batch)
        if not update_cols:
            # Nothing to update, just ignore conflicts
            upsert_stmt = stmt.on_conflict_do_nothing(index_elements=index_elements)
        else:
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_=update_cols
            )
        db.execute(upsert_stmt)
        total_upserted += len(batch)
    db.commit()
    return total_upserted

