import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load .env from backend root
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Try parent dir
    load_dotenv("../.env")
    DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("[ERROR] DATABASE_URL not found in .env")
    sys.exit(1)

print(f"Connecting to: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)

def add_column_if_not_exists(table, column, type_def):
    try:
        with engine.connect() as conn:
            # Check if column exists
            query = text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='{table}' AND column_name='{column}';
            """)
            result = conn.execute(query).fetchone()
            
            if not result:
                print(f"Adding column '{column}' to table '{table}'...")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {type_def};"))
                conn.commit()
                print(f"[SUCCESS] Column '{column}' added successfully.")
            else:
                print(f"[INFO] Column '{column}' already exists in table '{table}'.")
    except Exception as e:
        print(f"[ERROR] Error adding column '{column}' to '{table}': {e}")

def run_fixes():
    # Fix VerifiedNews
    add_column_if_not_exists("verified_news", "lang", "VARCHAR DEFAULT 'english'")
    add_column_if_not_exists("verified_news", "is_fake", "BOOLEAN DEFAULT FALSE")
    add_column_if_not_exists("verified_news", "flag_count", "INTEGER DEFAULT 0")
    add_column_if_not_exists("verified_news", "translation_cache", "JSON DEFAULT '{}'")
    add_column_if_not_exists("verified_news", "audio_url", "VARCHAR")
    
    # Fix TopicTracking
    add_column_if_not_exists("topic_tracking", "expires_at", "TIMESTAMP")
    add_column_if_not_exists("topic_tracking", "language", "VARCHAR DEFAULT 'english'")
    
    # Fix Advertisements
    add_column_if_not_exists("advertisements", "is_active", "BOOLEAN DEFAULT TRUE")
    add_column_if_not_exists("advertisements", "position", "VARCHAR DEFAULT 'both'")
    add_column_if_not_exists("advertisements", "target_platform", "VARCHAR DEFAULT 'both'")
    
    # Fix Users
    add_column_if_not_exists("users", "subscription_status", "VARCHAR DEFAULT 'free'")
    add_column_if_not_exists("users", "current_streak", "INTEGER DEFAULT 0")
    add_column_if_not_exists("users", "streak_history", "JSON DEFAULT '{}'")

if __name__ == "__main__":
    run_fixes()
    print("DONE.")
