"""
Kavach -- SQLAlchemy Engine & Session Factory
Supports PostgreSQL (production) or SQLite (fallback for testing).

Configure via environment variable:
  DATABASE_URL=postgresql+psycopg://user:password@host:port/dbname

If DATABASE_URL is not set, defaults to PostgreSQL on localhost.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# ─── Connection URL ───────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://kavach:kavach123@localhost:5432/kavach_db"
)

# ─── Engine ───────────────────────────────────────────────────────────────────

# For PostgreSQL + psycopg3: connection pool settings suited for sync FastAPI
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
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
    """
    Yields a SQLAlchemy session for use as a FastAPI dependency.
    Automatically closes the session after the request.

    Usage:
        @app.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
