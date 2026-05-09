# Backup of Cricket Live Score Logic
# Removed on: 2026-05-07

import os
import json
import logging
from datetime import datetime
from loguru import logger
from src.config import settings

# --- CACHES & GLOBALS ---
# This was at the top of web_dashboard.py
_cricket_cache = {"data": None, "timestamp": None}

# --- API ENDPOINT ---
# This was at @router.get("/api/cricket/live")
async def get_live_cricket():
    """Endpoint for the draggable cricket widget with real-time API data (Cached for 120s)."""
    global _cricket_cache
    
    # 1. Check Cache (2-minute TTL)
    now = datetime.now()
    if _cricket_cache["data"] and _cricket_cache["timestamp"]:
        if (now - _cricket_cache["timestamp"]).total_seconds() < 120:
            logger.debug("Serving Cricket Data from cache...")
            return _cricket_cache["data"]

    try:
        import requests
        api_key = settings.CRICKET_API_KEY or "8b90d819-4610-4484-8971-041c61c71f12"
        url = f"https://api.cricapi.com/v1/currentMatches?apikey={api_key}&offset=0"
        
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if data.get("status") != "success":
            reason = data.get('reason')
            logger.error(f"Cricket API Error: {reason}")
            
            # If blocked, definitely serve from cache if available, even if expired
            if "blocked" in str(reason).lower() and _cricket_cache["data"]:
                logger.warning("API blocked. Serving stale cricket cache.")
                return _cricket_cache["data"]
                
            # Fallback to scraper if API fails
            return await _get_live_cricket_scraped()
            
        matches = data.get("data", [])
        live_matches = []
        
        for m in matches:
            status = m.get("status", "")
            if not status: continue
            
            is_ended = m.get("matchEnded", False)
            title = m.get("name", "Cricket Match")
            score_list = m.get("score", [])
            
            scores = []
            for s in score_list:
                scores.append(f"{s.get('inning')}: {s.get('r')}/{s.get('w')} ({s.get('o')} ov)")
            
            short_score = " | ".join(scores) if scores else "Match starting soon..."
            
            live_matches.append({
                "name": title,
                "short_score": short_score,
                "status": status,
                "is_live": not is_ended
            })

        result = {"status": "success", "live": False, "message": "No live cricket matches found."}
        if live_matches:
            live_matches.sort(key=lambda x: x["is_live"], reverse=True)
            result = {
                "status": "success",
                "live": True,
                "matches": live_matches,
                "count": len(live_matches)
            }
        
        # Update Cache
        _cricket_cache["data"] = result
        _cricket_cache["timestamp"] = now
        return result

    except Exception as e:
        logger.error(f"Cricket API Failed: {e}")
        if _cricket_cache["data"]:
            return _cricket_cache["data"]
        return await _get_live_cricket_scraped()

# --- SCRAPER FALLBACK ---
async def _get_live_cricket_scraped():
    """Fallback scraper if API fails or for secondary data."""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        url = "https://www.cricbuzz.com/cricket-match/live-scores"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code != 200:
            return {"live": False, "message": "Cricket feed temporarily unavailable."}
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        matches_html = soup.find_all('div', class_='cb-mtch-lst')
        
        live_matches = []
        for match in matches_html:
            header = match.find('h3', class_='cb-lv-scr-mtch-hdr')
            if not header: continue
            
            title = header.text.strip()
            is_india = any(kw in title.lower() for kw in ["india", "ind ", " ind", "ipl", "wpl", "mumbai", "chennai", "delhi", "bangalore", "kolkata", "rajasthan", "punjab", "gujarat", "lucknow", "hyderabad", "rcb", "csk", "mi", "kkr", "dc", "pbks", "gt", "lsg", "srh"])
            
            status_div = match.find('div', class_='cb-text-live')
            if not status_div:
                # Try completed
                status_div = match.find('div', class_='cb-text-complete')
            
            if not status_div: continue
            
            score_div = match.find('div', class_='cb-scr-wgt-cont') or match.find('div', class_='cb-scr-wkt-line')
            short_score = score_div.text.strip() if score_div else "Live Tracking..."
            
            live_matches.append({
                "name": title,
                "short_score": short_score,
                "status": status_div.text.strip(),
                "is_india": is_india
            })

        if live_matches:
            live_matches.sort(key=lambda x: x["is_india"], reverse=True)
            return {
                "live": True,
                "matches": live_matches,
                "count": len(live_matches)
            }
        return {"live": False, "message": "No live cricket matches found."}
    except Exception as e:
        logger.error(f"Cricket Scraper Failed: {e}")
        return {"live": False, "message": "Cricket feed temporarily unavailable."}
