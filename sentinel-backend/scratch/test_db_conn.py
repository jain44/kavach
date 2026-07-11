import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://kavach:kavach123@localhost:5432/kavach_db"
)

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT version();")).fetchone()
        print("Successfully connected to Postgres!")
        print("Version:", res[0])
        
        # Check existing tables
        tables = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)).fetchall()
        print("Tables in public schema:", [t[0] for t in tables])
except Exception as e:
    print("Failed to connect to database:", e)
