import os
import sys
from sqlalchemy import text
from src.database.models import SessionLocal

def clear_old_news():
    print("STARTING DATABASE CLEANUP (News Articles Only)...")
    db = SessionLocal()
    try:
        # Tables to truncate in correct order for foreign keys
        tables = [
             "track_notifications",
             "breaking_news",
             "daily_digests",
             "verified_news",
             "raw_news"
        ]
        
        for table in tables:
            try:
                print(f"Truncating {table}...")
                db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
            except Exception as e:
                print(f"Warn: Could not truncate {table} directly ({e}). Trying DELETE...")
                db.execute(text(f"DELETE FROM {table}"))
        
        db.commit()
        print("SUCCESS: News records cleared. User history, bookmarks, and accounts preserved.")
    except Exception as e:
        db.rollback()
        print(f"FAILED: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_old_news()
