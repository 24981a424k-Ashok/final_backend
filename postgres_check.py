
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found in .env")
    exit(1)

print(f"Connecting to: {DATABASE_URL.split('@')[1]}") # Print host only for safety

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Check connection
        res = conn.execute(text("SELECT version();"))
        print(f"Connected! Postgres version: {res.fetchone()[0]}")
        
        # Check tables
        res = conn.execute(text("SELECT count(*) FROM verified_news;"))
        count = res.fetchone()[0]
        print(f"VerifiedNews count: {count}")
        
        # Check if we can fetch a few articles
        res = conn.execute(text("SELECT title FROM verified_news LIMIT 5;"))
        articles = res.fetchall()
        print("Latest 5 articles:")
        for a in articles:
            print(f"- {a[0]}")
            
except Exception as e:
    print(f"Database connection failed: {e}")
    exit(1)
