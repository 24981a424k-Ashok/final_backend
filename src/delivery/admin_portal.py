import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from src.database.models import SessionLocal, VerifiedNews, Advertisement, Newspaper, ProtocolHistory, SystemConfig
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin Portal"])
from src.utils.redis_cache import redis_cache
from src.database.session import get_db, SessionLocal
from src.config.settings import ADMIN_EMAIL, ADMIN_PASSWORD
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request, BackgroundTasks
import os

# Setup templates with failsafe fallback
templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web", "templates")
try:
    os.makedirs(templates_dir, exist_ok=True)
    fallback_file = os.path.join(templates_dir, "admin_dashboard_enhanced.html")
    if not os.path.exists(fallback_file):
        with open(fallback_file, "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html><html><body><h1>Admin Dashboard (Pure API Mode)</h1></body></html>")
except Exception as e:
    logger.error(f"Failsafe templates setup failed: {e}")
    # fallback to current directory to avoid crash
    templates_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        fallback_file = os.path.join(templates_dir, "admin_dashboard_enhanced.html")
        if not os.path.exists(fallback_file):
            with open(fallback_file, "w", encoding="utf-8") as f:
                f.write("<!DOCTYPE html><html><body><h1>Admin Dashboard (Pure API Mode)</h1></body></html>")
    except Exception as ie:
        logger.error(f"Secondary fallback templates setup failed: {ie}")

templates = Jinja2Templates(directory=templates_dir)

# --- Admin token from environment (NEVER hardcode in source) ---
_ADMIN_TOKEN = os.getenv("ADMIN_JWT_SECRET", os.getenv("ADMIN_SECRET_TOKEN"))
if not _ADMIN_TOKEN:
    import secrets
    _ADMIN_TOKEN = secrets.token_hex(32)
    logger.warning("ADMIN_JWT_SECRET not in env! Generated a random token for this session. Set it in .env for persistence.")

# --- Pydantic Schemas ---
class LoginRequest(BaseModel):
    email: str
    password: str

# --- Authentication ---
# --- Authentication Middleware ---
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
security = HTTPBearer()

async def verify_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # FIXED: Token read from environment, not hardcoded in source
    if not _ADMIN_TOKEN or credentials.credentials != _ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Neural Access Denied: Unauthorized")
    return True

@router.post("/login")
async def admin_login(payload: LoginRequest, db: Session = Depends(get_db)):
    # FIXED: Compare against env-var credentials, no hardcoded fallbacks
    if payload.email == ADMIN_EMAIL and payload.password == ADMIN_PASSWORD:
        log_protocol_action(db, 'auth_success', 'admin', None, f"Admin Login: {payload.email}")
        return {
            "status": "success",
            "token": _ADMIN_TOKEN,  # Read from env, not hardcoded
            "role": "admin"
        }
    
    raise HTTPException(status_code=401, detail="Neural Access Denied: Invalid Credentials")

# --- UI Route ---
@router.get("/dashboard", response_class=HTMLResponse)
async def serve_admin_dashboard(request: Request):
    """Serve the enhanced admin dashboard UI."""
    return templates.TemplateResponse("admin_dashboard_enhanced.html", {"request": request})

# --- Analytics & Stats ---
@router.get("/stats")
async def get_admin_stats(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    """Retrieve high-level system analytics for Play Store launch."""
    from src.database.models import User, VerifiedNews, RawNews, DailyDigest
    from datetime import datetime, timedelta
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    return {
        "status": "success",
        "counts": {
            "users": db.query(User).count(),
            "verified_articles": db.query(VerifiedNews).count(),
            "raw_collected": db.query(RawNews).count(),
            "digests": db.query(DailyDigest).count()
        },
        "engagement": {
            "active_today": db.query(User).filter(User.last_active_date >= today).count(),
            "premium_users": db.query(User).filter(User.subscription_status != "free").count()
        },
        "system": {
            "cycle_status": "Healthy",
            "db_engine": "Neural Edge (SQLite)",
            "uptime_nodes": 12
        }
    }


# --- Audit Helper ---
def log_protocol_action(db: Session, action: str, target: str, target_id: str = None, details: str = None):
    try:
        new_log = ProtocolHistory(
            action=action,
            target_type=target,
            target_id=target_id,
            admin_user="Ashok Reddy", # Superuser
            details=details
        )
        db.add(new_log)
        db.commit()
    except Exception as e:
        logger.error(f"Audit Log Failed: {e}")

# --- Pydantic Schemas ---
class AdCreate(BaseModel):
    image_url: str
    caption: Optional[str] = None
    position: str = "mobile"
    target_node: str = "Global"
    target_url: Optional[str] = None
    target_platform: str = "both"

class ArticleCreate(BaseModel):
    title: str
    content: str
    category: str
    sub_category: Optional[str] = None
    country: str = "Global"
    impact_score: int = 5

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    country: Optional[str] = None
    bias_rating: Optional[str] = None
    impact_score: Optional[int] = None
    credibility_score: Optional[float] = None
    lang: Optional[str] = None
    image_url_manual: Optional[str] = None
    image_url: Optional[str] = None
    why_it_matters: Optional[str] = None
    who_is_affected: Optional[str] = None
    access_link: Optional[str] = None
    short_term_impact: Optional[str] = None
    long_term_impact: Optional[str] = None
    sentiment: Optional[str] = None
    summary_bullets: Optional[List[str]] = None
    impact_tags: Optional[List[str]] = None
    redirect_url: Optional[str] = None

class AdUpdate(BaseModel):
    image_url: Optional[str] = None
    caption: Optional[str] = None
    position: Optional[str] = None
    target_node: Optional[str] = None
    target_url: Optional[str] = None
    target_platform: Optional[str] = None
    is_active: Optional[bool] = None

class NewspaperCreate(BaseModel):
    name: str
    url: str
    country: str = "Global"
    logo_text: Optional[str] = None
    logo_color: Optional[str] = None

class NewspaperUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    country: Optional[str] = None
    logo_text: Optional[str] = None
    logo_color: Optional[str] = None

# --- Article CRUD ---
@router.get("/articles")
async def get_admin_articles(category: Optional[str] = None, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    query = db.query(VerifiedNews)
    if category and category != "All":
        query = query.filter(VerifiedNews.category == category)
    articles = query.order_by(VerifiedNews.created_at.desc()).limit(100).all()
    return articles

@router.post("/articles")
async def create_admin_article(article: ArticleCreate, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    new_art = VerifiedNews(
        title=article.title,
        content=article.content,
        category=article.category,
        sub_category=article.sub_category,
        country=article.country,
        impact_score=article.impact_score,
        summary_bullets=["Verified manual injection"],
        bias_rating="Neutral",
        credibility_score=10.0,
        sentiment="Neutral",
        impact_tags=[],
        why_it_matters="Manual Admin Update",
        published_at=datetime.utcnow()
    )
    db.add(new_art)
    db.commit()
    db.refresh(new_art)
    log_protocol_action(db, 'deploy', 'article', str(new_art.id), f"Manual Article: {article.title}")
    await redis_cache.clear_pattern("uniarc:bootstrap:*")
    await redis_cache.clear_pattern("uniarc:student:*")
    return {"status": "success", "id": new_art.id}

@router.delete("/articles/{article_id}")
async def delete_admin_article(article_id: int, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    art = db.query(VerifiedNews).filter(VerifiedNews.id == article_id).first()
    if art:
        title = art.title
        db.delete(art)
        db.commit()
        log_protocol_action(db, 'purge', 'article', str(article_id), f"Purged: {title}")
        await redis_cache.clear_pattern("uniarc:bootstrap:*")
        await redis_cache.clear_pattern("uniarc:student:*")
    return {"status": "purged"}

@router.put("/articles/{article_id}")
async def update_admin_article(article_id: int, payload: ArticleUpdate, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    from src.database.models import VerifiedNews, RawNews
    import json
    
    art = db.query(VerifiedNews).filter(VerifiedNews.id == article_id).first()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
        
    if payload.title is not None:
        art.title = payload.title
    if payload.content is not None:
        art.content = payload.content
    elif payload.description is not None:
        art.content = payload.description
        
    if payload.category is not None:
        art.category = payload.category
    if payload.sub_category is not None:
        art.sub_category = payload.sub_category
    if payload.country is not None:
        art.country = payload.country
    if payload.bias_rating is not None:
        art.bias_rating = payload.bias_rating
    if payload.impact_score is not None:
        art.impact_score = payload.impact_score
    if payload.credibility_score is not None:
        art.credibility_score = payload.credibility_score
    if payload.lang is not None:
        art.lang = payload.lang
    if payload.why_it_matters is not None:
        art.why_it_matters = payload.why_it_matters
    if payload.who_is_affected is not None:
        art.who_is_affected = payload.who_is_affected
    if payload.short_term_impact is not None:
        art.short_term_impact = payload.short_term_impact
    if payload.long_term_impact is not None:
        art.long_term_impact = payload.long_term_impact
    if payload.sentiment is not None:
        art.sentiment = payload.sentiment
    if payload.summary_bullets is not None:
        art.summary_bullets = payload.summary_bullets
    if payload.impact_tags is not None:
        art.impact_tags = payload.impact_tags
        
    # Access/Image Link storage in analysis blob
    current_analysis = art.analysis or {}
    if isinstance(current_analysis, str):
        try:
            current_analysis = json.loads(current_analysis)
        except Exception:
            current_analysis = {}
            
    if payload.access_link is not None:
        current_analysis["access_link"] = payload.access_link
    if payload.image_url_manual is not None:
        current_analysis["image_url"] = payload.image_url_manual
    elif payload.image_url is not None:
        current_analysis["image_url"] = payload.image_url
        
    art.analysis = current_analysis
    
    # Update RawNews relationship if it exists
    if art.raw_news:
        if payload.redirect_url is not None and art.raw_news.url != payload.redirect_url:
            existing_url = db.query(RawNews).filter(RawNews.url == payload.redirect_url).first()
            if existing_url and existing_url.id != art.raw_news.id:
                raise HTTPException(status_code=400, detail="Redirect URL already exists in another node.")
            art.raw_news.url = payload.redirect_url
            
        if payload.title is not None:
            art.raw_news.title = payload.title
        if payload.content is not None:
            art.raw_news.description = payload.content
        elif payload.description is not None:
            art.raw_news.description = payload.description
        if payload.image_url_manual is not None:
            art.raw_news.url_to_image = payload.image_url_manual
        elif payload.image_url is not None:
            art.raw_news.url_to_image = payload.image_url

    db.commit()
    log_protocol_action(db, 'update', 'article', str(article_id), f"Updated: {art.title}")
    await redis_cache.clear_pattern("uniarc:bootstrap:*")
    await redis_cache.clear_pattern("uniarc:student:*")
    return {"status": "success", "id": article_id}

# --- Ad Management (CRUD) ---
@router.get("/ads")
async def get_admin_ads(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    return db.query(Advertisement).order_by(Advertisement.created_at.desc()).all()

@router.post("/ads")
async def create_admin_ad(ad: AdCreate, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    new_ad = Advertisement(
        image_url=ad.image_url,
        caption=ad.caption,
        position=ad.position,
        target_node=ad.target_node,
        target_url=ad.target_url,
        target_platform=ad.target_platform
    )
    db.add(new_ad)
    db.commit()
    db.refresh(new_ad)
    log_protocol_action(db, 'deploy', 'ad', str(new_ad.id), f"New Campaign Banner: {ad.caption}")
    await redis_cache.clear_pattern("uniarc:bootstrap:*")
    await redis_cache.clear_pattern("uniarc:student:*")
    return {"status": "success", "id": new_ad.id}

@router.delete("/ads/{ad_id}")
async def delete_admin_ad(ad_id: int, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    ad = db.query(Advertisement).filter(Advertisement.id == ad_id).first()
    if ad:
        db.delete(ad)
        db.commit()
        log_protocol_action(db, 'purge', 'ad', str(ad_id), "Purged campaign banner")
        await redis_cache.clear_pattern("uniarc:bootstrap:*")
        await redis_cache.clear_pattern("uniarc:student:*")
    return {"status": "purged"}

@router.put("/ads/{ad_id}")
async def update_admin_ad(ad_id: int, payload: AdUpdate, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    ad = db.query(Advertisement).filter(Advertisement.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad campaign banner not found")
    
    if payload.image_url is not None:
        ad.image_url = payload.image_url
    if payload.caption is not None:
        ad.caption = payload.caption
    if payload.position is not None:
        ad.position = payload.position
    if payload.target_node is not None:
        ad.target_node = payload.target_node
    if payload.target_url is not None:
        ad.target_url = payload.target_url
    if payload.target_platform is not None:
        ad.target_platform = payload.target_platform
    if payload.is_active is not None:
        ad.is_active = payload.is_active
        
    db.commit()
    log_protocol_action(db, 'update', 'ad', str(ad_id), f"Updated campaign banner: {ad.caption}")
    await redis_cache.clear_pattern("uniarc:bootstrap:*")
    await redis_cache.clear_pattern("uniarc:student:*")
    return {"status": "success", "id": ad_id}

# --- Source Management ---
@router.get("/newspapers")
async def get_admin_sources(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    return db.query(Newspaper).all()

@router.post("/newspapers")
async def create_admin_source(source: NewspaperCreate, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    existing = db.query(Newspaper).filter(Newspaper.url == source.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="Newspaper source URL already exists.")
        
    new_source = Newspaper(
        name=source.name,
        url=source.url,
        country=source.country,
        logo_text=source.logo_text,
        logo_color=source.logo_color
    )
    db.add(new_source)
    db.commit()
    db.refresh(new_source)
    log_protocol_action(db, 'deploy', 'source', str(new_source.id), f"Registered source: {source.name}")
    return {"status": "success", "id": new_source.id}

@router.put("/newspapers/{source_id}")
async def update_admin_source(source_id: int, payload: NewspaperUpdate, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    source = db.query(Newspaper).filter(Newspaper.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Newspaper source not found")
        
    if payload.name is not None:
        source.name = payload.name
    if payload.url is not None:
        existing = db.query(Newspaper).filter(Newspaper.url == payload.url).first()
        if existing and existing.id != source_id:
            raise HTTPException(status_code=400, detail="Newspaper source URL already exists on another node.")
        source.url = payload.url
    if payload.country is not None:
        source.country = payload.country
    if payload.logo_text is not None:
        source.logo_text = payload.logo_text
    if payload.logo_color is not None:
        source.logo_color = payload.logo_color
        
    db.commit()
    log_protocol_action(db, 'update', 'source', str(source_id), f"Updated source: {source.name}")
    return {"status": "success", "id": source_id}

@router.delete("/newspapers/{source_id}")
async def delete_admin_source(source_id: int, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    source = db.query(Newspaper).filter(Newspaper.id == source_id).first()
    if source:
        db.delete(source)
        db.commit()
        log_protocol_action(db, 'purge', 'source', str(source_id), f"Unregistered source: {source.name}")
    return {"status": "purged"}

# --- System Audit & History ---
@router.post("/refresh-digest")
async def force_intelligence_sync(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    try:
        from src.scheduler.task_scheduler import run_news_cycle
        import threading
        # Run in background to avoid timeout
        def run_sync():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_news_cycle())
                loop.close()
            except Exception as e:
                logger.error(f"Background Sync Failed: {e}")

        threading.Thread(target=run_sync, daemon=True).start()
        log_protocol_action(db, 'sync_trigger', 'intelligence_nodes', None, "Manual Intelligence Refresh Initiated")
        return {"status": "sync_initiated", "message": "Neural nodes are fetching fresh intelligence."}
    except Exception as e:
        logger.error(f"Sync Trigger Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_admin_history(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    return db.query(ProtocolHistory).order_by(ProtocolHistory.timestamp.desc()).limit(100).all()

# --- Config Management ---
@router.get("/config")
async def get_admin_config(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    configs = db.query(SystemConfig).all()
    return {c.config_key: c.config_value for c in configs}

@router.post("/config")
async def update_admin_config(payload: Dict[str, str], db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    for key, value in payload.items():
        cfg = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        if cfg:
            cfg.config_value = value
        else:
            db.add(SystemConfig(config_key=key, config_value=value))
    db.commit()
    log_protocol_action(db, 'config_update', 'system', None, f"Updated System Parameters: {list(payload.keys())}")
    return {"status": "updated"}

# --- Pipeline & Key Pool Control ---
@router.post("/trigger-ingest")
async def trigger_news_ingestion(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    try:
        from src.scheduler.task_scheduler import run_news_cycle
        import threading
        # Launch cycle asynchronously in the background
        threading.Thread(target=lambda: asyncio.run(run_news_cycle()), daemon=True).start()
        log_protocol_action(db, 'ingest_trigger', 'news_pipeline', None, "Manual News Ingestion Pipeline Started")
        return {"status": "success", "message": "News ingestion cycle running in background."}
    except Exception as e:
        logger.error(f"Ingestion trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear-cache")
async def clear_translation_cache(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    try:
        num_updated = db.query(VerifiedNews).update({VerifiedNews.translation_cache: {}})
        db.commit()
        log_protocol_action(db, 'clear_cache', 'translation_cache', None, f"Cleared translation cache for {num_updated} articles")
        return {"status": "success", "articles_cleared": num_updated}
    except Exception as e:
        db.rollback()
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/keypool-status")
async def get_keypool_status(auth: bool = Depends(verify_admin)):
    from src.config import settings
    
    openai_keys = []
    for i, k in enumerate(settings.OPENAI_API_KEYS):
        masked = f"{k[:8]}...{k[-4:]}" if len(k) > 12 else k
        openai_keys.append({"index": i + 1, "key": masked, "status": "active"})
        
    groq_keys = []
    for i, k in enumerate(settings.GROQ_API_KEYS):
        masked = f"{k[:6]}...{k[-4:]}" if len(k) > 10 else k
        groq_keys.append({"index": i + 1, "key": masked, "status": "active"})
        
    return {
        "status": "success",
        "total": len(openai_keys) + len(groq_keys),
        "openai": {"count": len(openai_keys), "keys": openai_keys},
        "groq": {"count": len(groq_keys), "keys": groq_keys}
    }

