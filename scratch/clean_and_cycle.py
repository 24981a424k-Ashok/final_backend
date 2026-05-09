
import os
import sys

# PATH SETUP
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import asyncio
from sqlalchemy.orm import Session
from src.database.models import SessionLocal, VerifiedNews, RawNews, DailyDigest, SystemConfig, TopicTracking
from src.scheduler.task_scheduler import run_news_cycle
from loguru import logger

async def clean_and_start():
    logger.info("Cleaning database for fresh start...")
    db = SessionLocal()
    try:
        # Delete old data
        db.query(VerifiedNews).delete()
        db.query(RawNews).delete()
        db.query(DailyDigest).delete()
        db.query(TopicTracking).delete()
        
        # Reset last cycle run
        cfg = db.query(SystemConfig).filter(SystemConfig.config_key == "last_news_cycle_run").first()
        if cfg:
            cfg.config_value = "Never"
        else:
            db.add(SystemConfig(config_key="last_news_cycle_run", config_value="Never"))
            
        db.commit()
        logger.info("Database cleaned successfully.")
        
        logger.info("Starting fresh 15-minute news cycle...")
        await run_news_cycle()
        logger.info("News cycle completed.")
        
        # Verify
        count = db.query(VerifiedNews).count()
        logger.info(f"Verification: {count} fresh articles ingested into PostgreSQL.")
        
    except Exception as e:
        logger.error(f"Failed to clean and start: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(clean_and_start())
