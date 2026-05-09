from src.database.models import SessionLocal, VerifiedNews
import json

def check_translations():
    db = SessionLocal()
    try:
        # Check for articles that have a translation cache
        articles = db.query(VerifiedNews).filter(VerifiedNews.translation_cache != None).limit(5).all()
        if not articles:
            print("No translation cache found in database.")
            return

        print(f"Found {len(articles)} articles with translation cache.")
        for art in articles:
            cache = art.translation_cache
            if isinstance(cache, str):
                try: cache = json.loads(cache)
                except: pass
            
            langs = list(cache.keys()) if isinstance(cache, dict) else []
            print(f"Article ID: {art.id}, Languages cached: {langs}")
            if cache:
                first_lang = langs[0] if langs else None
                if first_lang:
                    print(f"  Sample {first_lang} title: {cache[first_lang].get('title', 'N/A')[:50]}...")
    finally:
        db.close()

if __name__ == "__main__":
    check_translations()
