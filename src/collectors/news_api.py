from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
import time
from newsapi import NewsApiClient
from src.config.settings import NEWS_API_KEYS
from src.database.models import SessionLocal, RawNews

logger = logging.getLogger(__name__)

class NewsCollector:
    _key_status = {} # Class-level health tracker

    def __init__(self):
        self.keys = NEWS_API_KEYS
        if not self.keys:
            logger.warning("NewsAPI Keys are missing!")

    def _get_best_client(self):
        """Rotate through keys to find one that isn't on cooldown."""
        for key in self.keys:
            status = self._key_status.get(key, {"state": "active", "reset_at": 0})
            if status["state"] == "active" or time.time() > status["reset_at"]:
                self._key_status[key] = {"state": "active", "reset_at": 0}
                return NewsApiClient(api_key=key), key
        return None, None

    def _mark_key_limited(self, key: str, hours: int = 24, dead: bool = False):
        """Cool down or kill a key."""
        if dead:
            logger.error(f"NewsAPI: Key {key[:8]}... is INVALID. Disabling for this session.")
            self._key_status[key] = {"state": "dead", "reset_at": time.time() + (72 * 3600)}
        else:
            logger.warning(f"NewsAPI: Key {key[:8]}... hit quota. Cooling down for {hours}h.")
            self._key_status[key] = {
                "state": "limited",
                "reset_at": time.time() + (hours * 3600)
            }

    def fetch_recent_news(self, query: str = None, domains: str = None, categories: str = None) -> int:
        """
        Fetch news from the last 24 hours and save to DB.
        Uses key pooling to maximize quota.
        """
        while True:
            client, active_key = self._get_best_client()
            if not client:
                logger.error("All NewsAPI keys are currently exhausted, invalid, or limited.")
                return 0

            all_articles = []
            
            try:
                # 1. General Top Headlines
                try:
                    res = client.get_top_headlines(language='en', page_size=70)
                    if res.get('status') == 'ok':
                        all_articles.extend(res.get('articles', []))
                    elif res.get('code') == 'apiKeyInvalid':
                        self._mark_key_limited(active_key, dead=True)
                        continue # Try next key
                except Exception as e:
                    if "rateLimited" in str(e) or "429" in str(e) or "403" in str(e):
                        self._mark_key_limited(active_key)
                        return 0 # Stop this run
                    if "apiKeyInvalid" in str(e):
                        self._mark_key_limited(active_key, dead=True)
                        continue # Try next key
                    logger.error(f"NewsAPI General failed: {e}")

            # 2. Business Headlines
            try:
                res = client.get_top_headlines(language='en', category='business', country='in', page_size=30)
                if res['status'] == 'ok':
                    all_articles.extend(res.get('articles', []))
            except Exception as e:
                logger.warning(f"NewsAPI Business failed: {e}")

            # 3. Sports Headlines
            try:
                res = client.get_top_headlines(language='en', category='sports', page_size=30)
                if res['status'] == 'ok':
                    all_articles.extend(res.get('articles', []))
            except Exception as e:
                logger.warning(f"NewsAPI Sports failed: {e}")

            # 4. Target Countries
            for country_code in ['jp', 'us']:
                try:
                    res = client.get_top_headlines(
                        language='en' if country_code != 'jp' else None,
                        country=country_code,
                        page_size=20
                    )
                    if res['status'] == 'ok':
                        articles = res.get('articles', [])
                        for a in articles:
                            a['target_country'] = country_code
                        all_articles.extend(articles)
                except Exception as ce:
                    logger.warning(f"NewsAPI {country_code} failed: {ce}")

            saved_count = self._save_articles(all_articles)
            return saved_count
            
        except Exception as e:
            logger.error(f"Error in NewsAPI collection cycle: {e}")
            return 0

    def _save_articles(self, articles: List[Dict[str, Any]]) -> int:
        session = SessionLocal()
        count = 0
        seen_urls = set()
        try:
            for article in articles:
                url = article.get('url')
                if not url:
                    continue
                
                # Check for duplicates
                # Check for duplicates (DB + Current Batch)
                if url in seen_urls:
                    continue
                
                exists = session.query(RawNews).filter(RawNews.url == url).first()
                if exists:
                    continue
                
                seen_urls.add(url)
                
                # Parse date
                pub_date = article.get('publishedAt')
                if pub_date:
                    try:
                        # NewsAPI format: 2024-01-23T12:00:00Z
                        pub_dt = datetime.strptime(pub_date, "%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        pub_dt = datetime.utcnow()
                else:
                    pub_dt = datetime.utcnow()

                raw_news = RawNews(
                    source_id=article.get('source', {}).get('id'),
                    source_name=article.get('source', {}).get('name'),
                    author=article.get('author'),
                    title=article.get('title'),
                    description=article.get('description'),
                    url=url,
                    url_to_image=article.get('urlToImage'),
                    published_at=pub_dt,
                    content=article.get('content'),
                    country=article.get('target_country')
                )
                session.add(raw_news)
                count += 1
            
            session.commit()
            logger.info(f"Saved {count} new articles.")
            return count
        except Exception as e:
            logger.error(f"Database error: {e}")
            session.rollback()
            return 0
        finally:
            session.close()

if __name__ == "__main__":
    # Test run
    collector = NewsCollector()
    collector.fetch_recent_news()
