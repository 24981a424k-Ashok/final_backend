from src.database.models import SessionLocal, VerifiedNews
import json

def find_translations():
    db = SessionLocal()
    try:
        # Check for articles that have a translation cache with actual keys
        articles = db.query(VerifiedNews).all()
        found = 0
        for art in articles:
            cache = art.translation_cache
            if not cache: continue
            if isinstance(cache, str):
                try: cache = json.loads(cache)
                except: continue
            
            if isinstance(cache, dict) and cache:
                langs = list(cache.keys())
                print(f"Article ID: {art.id}, Languages cached: {langs}")
                found += 1
                if found >= 5: break
        
        if found == 0:
            print("No translations found in the entire database.")
    finally:
        db.close()

if __name__ == "__main__":
    find_translations()
