import sys
import os
from pathlib import Path
import asyncio
import httpx
from sqlalchemy import text, create_engine

# Fix paths to allow importing from src
sys.path.append(str(Path(__file__).resolve().parent.parent))

try:
    from src.config.settings import DATABASE_URL, CRICKET_API_KEY
except ImportError:
    print("[FAIL] Critical Error: Could not import settings. Ensure you are running from the backend root.")
    sys.exit(1)

async def check_database():
    print("--- [1/4] Checking PostgreSQL Connection ---")
    if not DATABASE_URL:
        print("[FAIL] DATABASE_URL is not set!")
        return

    try:
        # Standardize URL for check
        url = DATABASE_URL
        if url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql+psycopg2://", "postgresql://")
        
        # Use sync engine for simple connectivity check
        engine = create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).fetchone()
            if result and result[0] == 1:
                print("[OK] PostgreSQL Connection: OK (Verified via SELECT 1)")
            else:
                print("[WARN] PostgreSQL Connection: Connected, but query failed.")
    except Exception as e:
        print(f"[FAIL] PostgreSQL Connection Failed: {e}")
        print("   TIP: Check if DATABASE_URL is correct and the database is accessible.")

async def check_cricket_api():
    print("\n--- [2/4] Checking Cricket API ---")
    if not CRICKET_API_KEY:
        print("[FAIL] CRICKET_API_KEY is missing!")
        return
    
    try:
        url = f"https://api.cricapi.com/v1/currentMatches?apikey={CRICKET_API_KEY}&offset=0"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success':
                    matches = data.get('data', [])
                    print(f"[OK] Cricket API: OK (Status: Success, Matches: {len(matches)})")
                else:
                    print(f"[FAIL] Cricket API Error: {data.get('reason', 'Unknown error from API')}")
            else:
                print(f"[FAIL] Cricket API HTTP Error: {resp.status_code}")
    except Exception as e:
        print(f"[FAIL] Cricket API Connection Failed: {e}")

async def check_firebase():
    print("\n--- [3/4] Checking Firebase Admin SDK ---")
    try:
        import firebase_admin
        from firebase_admin import auth
        
        # Check if already initialized
        try:
            firebase_admin.get_app()
        except ValueError:
            # Need to initialize if not done
            from src.config.firebase_config import initialize_firebase
            initialize_firebase()
            
        # Simple list users to check auth connectivity
        auth.list_users(max_results=1)
        print("[OK] Firebase Admin SDK: OK (Initialized and Auth accessible)")
    except Exception as e:
        print(f"[FAIL] Firebase Admin SDK Failed: {e}")

async def check_backend_health():
    print("\n--- [4/4] Checking Backend Local Health ---")
    try:
        # Check if the backend process is running locally on port 8000
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:8000/api/v2/health", timeout=3.0)
            if resp.status_code == 200:
                print(f"[OK] Backend Health Endpoint: OK ({resp.json()})")
            else:
                print(f"[WARN] Backend Health Endpoint returned {resp.status_code}")
    except Exception:
        print("[INFO] Backend process not detected on localhost:8000. Skipping live endpoint check.")

async def main():
    print("========================================")
    print("   AI NEWS PLATFORM STABILITY CHECK     ")
    print("========================================\n")
    
    await check_database()
    await check_cricket_api()
    await check_firebase()
    await check_backend_health()
    
    print("\n========================================")
    print("       STABILITY CHECK COMPLETE         ")
    print("========================================")

if __name__ == "__main__":
    asyncio.run(main())
