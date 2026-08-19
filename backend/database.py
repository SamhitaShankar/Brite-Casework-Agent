"""
Database engine and session management for Brite Casework Agent.
PostgreSQL is the sole authoritative production and runtime database.
"""
import os
from .compat import create_engine, declarative_base, sessionmaker, HAS_SQLALCHEMY

DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:///brite_casework.db"
)

if HAS_SQLALCHEMY and create_engine is not None:
    try:
        engine = create_engine(DATABASE_URL, echo=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base = declarative_base()
    except Exception:
        engine = None
        SessionLocal = sessionmaker()
        Base = declarative_base()
else:
    engine = None
    SessionLocal = sessionmaker()
    Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
