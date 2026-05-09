import asyncio
import sys
import os
from pathlib import Path
import httpx
from sqlalchemy import text, create_engine
from loguru import logger

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))

from src.config import settings
from src.analysis.llm_analyzer import LLMAnalyzer
from src.utils.translator import NewsTranslator
from src.config.firebase_config import initialize_firebase

async def check_database():
    print("\n--- [1/5] Checking Database Node ---")
    if not settings.DATABASE_URL:
        print(" [FAIL] DATABASE_URL is not set!")
        return False

    try:
        url = settings.DATABASE_URL
        if url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql+psycopg2://", "postgresql://")
        
        engine = create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).fetchone()
            if result and result[0] == 1:
                print(" [OK] Database Connection: SUCCESS")
                return True
            else:
                print(" [WARN] Database Connection: CONNECTED (but health query failed)")
                return False
    except Exception as e:
        print(f" [FAIL] Database Connection FAILED: {str(e).encode('ascii', 'ignore').decode()}")
        return False

async def check_ai_pool():
    print("\n--- [2/5] Checking AI Fallback Pool ---")
    analyzer = LLMAnalyzer()
    print(f" - Configured Keys: {len(analyzer.openai_keys)} OpenAI, {len(analyzer.groq_keys)} Groq")
    
    if not analyzer.openai_keys and not analyzer.groq_keys:
        print(" [FAIL] AI Pool is EMPTY! Check .env and settings.py")
        return False

    test_article = {"title": "Health Check", "content": "Verifying AI connectivity."}
    try:
        # Test one analysis to verify the primary provider
        res = await analyzer.analyze_batch([test_article])
        if res and res[0].get("category"):
            print(f" [OK] AI Analysis SUCCESS (Provider: {analyzer._last_provider if hasattr(analyzer, '_last_provider') else 'Unknown'})")
            return True
        else:
            print(" [WARN] AI Analysis returned unexpected results.")
            return False
    except Exception as e:
        print(f" [FAIL] AI Pool Verification FAILED: {str(e).encode('ascii', 'ignore').decode()}")
        return False

async def check_firebase():
    print("\n--- [3/5] Checking Firebase Node ---")
    try:
        initialize_firebase()
        from firebase_admin import auth
        auth.list_users(max_results=1)
        print(" [OK] Firebase Admin SDK: SUCCESS")
        return True
    except Exception as e:
        print(f" [FAIL] Firebase Verification FAILED: {str(e).encode('ascii', 'ignore').decode()}")
        return False

async def check_news_apis():
    print("\n--- [4/5] Checking News API Nodes ---")
    success = True
    
    # NewsAPI
    if settings.NEWS_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://newsapi.org/v2/top-headlines?country=us&apiKey={settings.NEWS_API_KEY}", timeout=5)
                if resp.status_code == 200:
                    print(" [OK] NewsAPI: SUCCESS")
                else:
                    print(f" [FAIL] NewsAPI: FAILED (HTTP {resp.status_code})")
                    success = False
        except Exception as e:
            print(f" [FAIL] NewsAPI: FAILED ({str(e).encode('ascii', 'ignore').decode()})")
            success = False
    else:
        print(" [WARN] NewsAPI: KEY MISSING")

    # GNews
    if settings.GNEWS_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://gnews.io/api/v4/top-headlines?token={settings.GNEWS_API_KEY}&lang=en", timeout=5)
                if resp.status_code == 200:
                    print(" [OK] GNews API: SUCCESS")
                else:
                    print(f" [FAIL] GNews API: FAILED (HTTP {resp.status_code})")
                    success = False
        except Exception as e:
            print(f" [FAIL] GNews API: FAILED ({str(e).encode('ascii', 'ignore').decode()})")
            success = False
    else:
        print(" [WARN] GNews API: KEY MISSING")
        
    return success

async def check_external_services():
    print("\n--- [5/5] Checking External Integration Nodes ---")
    # Twilio
    if os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"):
        try:
            print(" [OK] Twilio Configuration: DETECTED")
        except:
            print(" [FAIL] Twilio Helper: IMPORT FAILED")
    else:
        print(" [WARN] Twilio: CONFIG MISSING")
    return True

async def main():
    print("========================================")
    print("   AI NEWS AGENT MASTER HEALTH CHECK    ")
    print("========================================\n")
    
    results = await asyncio.gather(
        check_database(),
        check_ai_pool(),
        check_firebase(),
        check_news_apis(),
        check_external_services()
    )
    
    print("\n========================================")
    if all(results):
        print("   ALL NODES OPERATIONAL: [ PASS ]     ")
    else:
        print("   SOME NODES FAILED: [ ACTION REQ ]   ")
    print("========================================")

if __name__ == "__main__":
    asyncio.run(main())
