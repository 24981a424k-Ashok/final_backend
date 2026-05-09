import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.models import Base
from sqlalchemy import create_engine, text
from src.config import settings

def migrate():
    print(f"Connecting to: {settings.DATABASE_URL}")
    engine = create_engine(settings.DATABASE_URL)
    
    # Create all tables
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")
    
    # Clear existing news tables to start fresh as requested
    with engine.connect() as conn:
        print("Clearing news tables for a fresh start...")
        conn.execute(text("TRUNCATE TABLE verified_news CASCADE;"))
        conn.execute(text("TRUNCATE TABLE raw_news CASCADE;"))
        conn.execute(text("TRUNCATE TABLE daily_digests CASCADE;"))
        conn.commit()
        print("Fresh start initialized. News tables are empty.")

if __name__ == "__main__":
    migrate()
