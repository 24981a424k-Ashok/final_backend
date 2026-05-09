
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the project root to sys.path
sys.path.append(os.getcwd())

from src.database.models import RawNews, VerifiedNews, SessionLocal

def check_db():
    db = SessionLocal()
    try:
        raw_count = db.query(RawNews).count()
        verified_count = db.query(VerifiedNews).count()
        print(f"RawNews count: {raw_count}")
        print(f"VerifiedNews count: {verified_count}")
        
        # Check last 5 verified news
        latest = db.query(VerifiedNews).order_by(VerifiedNews.id.desc()).limit(5).all()
        for i, n in enumerate(latest):
            print(f"{i+1}. {n.title} (Lang: {n.lang}, Category: {n.category})")
            
    except Exception as e:
        print(f"Error checking DB: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
