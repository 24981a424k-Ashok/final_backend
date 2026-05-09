import os
import sys
from pathlib import Path

# Setup path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.database.models import SessionLocal, RawNews, VerifiedNews
from loguru import logger

def cleanup():
    db = SessionLocal()
    try:
        logger.info("Cleaning up old news articles from PostgreSQL...")
        
        # Delete verified news first (FK constraint)
        verified_deleted = db.query(VerifiedNews).delete()
        logger.info(f"Deleted {verified_deleted} verified news articles.")
        
        # Delete raw news
        raw_deleted = db.query(RawNews).delete()
        logger.info(f"Deleted {raw_deleted} raw news articles.")
        
        db.commit()
        logger.info("Database cleanup complete.")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Cleanup failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()
