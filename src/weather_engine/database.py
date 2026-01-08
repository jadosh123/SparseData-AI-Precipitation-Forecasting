# src/weather_engine/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Get the URL (Defaults to SQLite if env var is missing)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./weather.db")

# 2. Configure for SQLite Concurrency
# SQLite doesn't like multiple threads sharing a connection by default.
# We must disable this check for FastAPI/Web usage.
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}

# 3. Create the Engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
)

# 4. Create Session Factory (for usage in scripts)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. Base class for your ORM Models (Optional, but recommended)
Base = declarative_base()