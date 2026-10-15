"""
Database configuration.

Defaults to SQLite for zero-config local runs and CI. Swap to Postgres in
production by setting DATABASE_URL, e.g.:
    postgresql+psycopg2://user:pass@host:5432/waypoint
No other code changes needed — SQLAlchemy handles the dialect switch.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./waypoint.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
