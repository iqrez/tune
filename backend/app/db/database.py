import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

# Absolute path to scratch directory to avoid relative path issues when running uvicorn
DB_DIR = os.path.join(os.path.dirname(__file__), '..', '..')
DB_PATH = os.path.join(DB_DIR, "basetune.db")

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class DBVehicleProfile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, index=True) # vehicle_id mapped here
    name = Column(String, index=True) # E.g., "Rezi's B18C"
    profile_data_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class DBSnapshot(Base):
    """Stores the append-only audit trail"""
    __tablename__ = "snapshots"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True)
    snapshot_json = Column(Text, nullable=False)
    signature = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Ensure tables are created
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
