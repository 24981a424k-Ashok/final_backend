import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException, Body, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.database.models import SessionLocal, VerifiedNews, Advertisement, Newspaper, ProtocolHistory, SystemConfig, RawNews, DailyDigest, User
from src.database.session import get_db
from src.config.settings import ADMIN_EMAIL, ADMIN_PASSWORD
from src.delivery.web_dashboard import log_protocol_action
from src.scheduler.task_scheduler import run_news_cycle
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin Portal"])

# Setup templates
templates = Jinja2Templates(directory="web/templates")

# --- Admin token ---
_ADMIN_TOKEN = os.getenv("ADMIN_JWT_SECRET", os.getenv("ADMIN_SECRET_TOKEN"))
if not _ADMIN_TOKEN:
    import secrets
    _ADMIN_TOKEN = secrets.token_hex(32)
    logger.warning("ADMIN_JWT_SECRET not in env! Generated a random token.")

# --- Authentication ---
security = HTTPBearer()

async def verify_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not _ADMIN_TOKEN or credentials.credentials != _ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Neural Access Denied: Unauthorized")
    return True

# --- Pydantic Schemas ---
class LoginRequest(BaseModel):
    email: str
    password: str

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
    bias_rating: Optional[str] = "Neutral"
    credibility_score: Optional[float] = 1.0
    why_it_matters: Optional[str] = None
    who_is_affected: Optional[str] = None
    short_term_impact: Optional[str] = None
    long_term_impact: Optional[str] = None
    summary_bullets: Optional[List[str]] = []
    impact_tags: Optional[List[str]] = []
    sentiment: Optional[str] = "Neutral"
    lang: Optional[str] = "english"
    image_url_manual: Optional[str] = None
    access_link: Optional[str] = None

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    country: Optional[str] = None
    impact_score: Optional[int] = None
    bias_rating: Optional[str] = None
    credibility_score: Optional[float] = None
    why_it_matters: Optional[str] = None
    who_is_affected: Optional[str] = None
    short_term_impact: Optional[str] = None
    long_term_impact: Optional[str] = None
    summary_bullets: Optional[List[str]] = None
    impact_tags: Optional[List[str]] = None
    sentiment: Optional[str] = None
    lang: Optional[str] = None
    image_url_manual: Optional[str] = None
    access_link: Optional[str] = None

class AdUpdate(BaseModel):
    image_url: Optional[str] = None
    caption: Optional[str] = None
    position: Optional[str] = None
    target_node: Optional[str] = None
    target_url: Optional[str] = None
    target_platform: Optional[str] = None
    is_active: Optional[bool] = None

@router.post("/login")
async def admin_login(payload: LoginRequest, db: Session = Depends(get_db)):
    if payload.email == ADMIN_EMAIL and payload.password == ADMIN_PASSWORD:
        return {"status": "success", "token": _ADMIN_TOKEN, "role": "admin"}
    raise HTTPException(status_code=401, detail="Invalid Credentials")

@router.get("/dashboard", response_class=HTMLResponse)
async def serve_admin_dashboard(request: Request):
    return templates.TemplateResponse("admin_dashboard_enhanced.html", {"request": request})

@router.get("/stats")
async def get_admin_stats(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    return {
        "status": "success",
        "counts": {
            "users": db.query(User).count(),
            "verified_articles": db.query(VerifiedNews).count(),
            "raw_collected": db.query(RawNews).count(),
            "digests": db.query(DailyDigest).count(),
            "advertisements": db.query(Advertisement).count(),
            "newspapers": db.query(Newspaper).count(),
            "sectors": db.query(text("SELECT COUNT(DISTINCT category) FROM verified_news")).scalar() or 0,
            "terminals": db.query(text("SELECT COUNT(DISTINCT source_name) FROM verified_news")).scalar() or 0
        }
    }

@router.post("/articles")
async def create_admin_article(article: ArticleCreate, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    try:
        new_art = VerifiedNews(
            title=article.title,
            content=article.content,
            category=article.category,
            sub_category=article.sub_category,
            country=article.country,
            impact_score=article.impact_score,
            bias_rating=article.bias_rating,
            credibility_score=article.credibility_score,
            why_it_matters=article.why_it_matters,
            who_is_affected=article.who_is_affected,
            short_term_impact=article.short_term_impact,
            long_term_impact=article.long_term_impact,
            summary_bullets=article.summary_bullets,
            impact_tags=article.impact_tags,
            sentiment=article.sentiment,
            lang=article.lang,
            image_url_manual=article.image_url_manual,
            access_link=article.access_link,
            published_at=datetime.utcnow()
        )
        db.add(new_art)
        db.commit()
        db.refresh(new_art)
        log_protocol_action(db, "deploy", "article", str(new_art.id), details=f"Manual deployment: {new_art.title}")
        return {"status": "success", "article_id": new_art.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/articles/{article_id}")
async def update_article(article_id: int, article: ArticleUpdate, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    db_art = db.query(VerifiedNews).filter(VerifiedNews.id == article_id).first()
    if not db_art:
        raise HTTPException(status_code=404, detail="Article not found")
    update_data = article.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_art, key, value)
    db_art.translation_cache = {}
    db.commit()
    log_protocol_action(db, "update", "article", str(article_id), details=f"Update: {db_art.title}")
    return {"status": "success"}

@router.delete("/articles/{article_id}")
async def delete_admin_article(article_id: int, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    art = db.query(VerifiedNews).filter(VerifiedNews.id == article_id).first()
    if art:
        db.delete(art)
        db.commit()
        log_protocol_action(db, 'purge', 'article', str(article_id))
    return {"status": "purged"}

@router.post("/ads")
async def create_admin_ad(ad: AdCreate, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    new_ad = Advertisement(**ad.dict())
    db.add(new_ad)
    db.commit()
    db.refresh(new_ad)
    log_protocol_action(db, 'deploy', 'ad', str(new_ad.id))
    return {"status": "success", "id": new_ad.id}

@router.put("/ads/{ad_id}")
async def update_ad(ad_id: int, ad: AdUpdate, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    db_ad = db.query(Advertisement).filter(Advertisement.id == ad_id).first()
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    update_data = ad.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_ad, key, value)
    db.commit()
    log_protocol_action(db, "update", "ad", str(ad_id))
    return {"status": "success"}

@router.delete("/ads/{ad_id}")
async def delete_admin_ad(ad_id: int, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    ad = db.query(Advertisement).filter(Advertisement.id == ad_id).first()
    if ad:
        db.delete(ad)
        db.commit()
        log_protocol_action(db, 'purge', 'ad', str(ad_id))
    return {"status": "purged"}

@router.post("/trigger-ingest")
async def trigger_ingest(background_tasks: BackgroundTasks, auth: bool = Depends(verify_admin)):
    background_tasks.add_task(run_news_cycle)
    return {"status": "success", "message": "Intelligence cycle initiated."}

@router.post("/refresh-digest")
async def refresh_digest(background_tasks: BackgroundTasks, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    from src.digest.generator import DigestGenerator
    generator = DigestGenerator()
    background_tasks.add_task(generator.create_daily_digest, db)
    return {"status": "success", "message": "Digest refresh initiated."}

@router.post("/clear-cache")
async def clear_cache(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    try:
        count = db.query(VerifiedNews).update({VerifiedNews.translation_cache: {}})
        db.commit()
        return {"status": "success", "articles_cleared": count}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/keypool-status")
async def keypool_status(auth: bool = Depends(verify_admin)):
    from src.config import settings
    def mask(k): return f"{k[:6]}...{k[-4:]}" if k else "MISSING"
    return {
        "openai": {"total": len(settings.OPENAI_API_KEYS), "keys": [{"key": mask(k)} for k in settings.OPENAI_API_KEYS]},
        "groq": {"total": len(settings.GROQ_API_KEYS), "keys": [{"key": mask(k)} for k in settings.GROQ_API_KEYS]}
    }

@router.get("/health")
async def health_check(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    try:
        db.execute(text("SELECT 1"))
        db_status, article_count = "UP", db.query(VerifiedNews).count()
    except:
        db_status, article_count = "DOWN", 0
    return {"status": "healthy", "database": {"status": db_status, "article_count": article_count}}

@router.get("/newspapers")
async def get_admin_sources(db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    return db.query(Newspaper).all()

@router.delete("/newspapers/{source_id}")
async def delete_admin_source(source_id: int, db: Session = Depends(get_db), auth: bool = Depends(verify_admin)):
    source = db.query(Newspaper).filter(Newspaper.id == source_id).first()
    if source:
        db.delete(source)
        db.commit()
    return {"status": "purged"}

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
