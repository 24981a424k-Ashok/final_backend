"""
AI Briefs Collector — "Stay Ahead with AI"
Collects AI-specific content every 15 minutes from:
  - RSS Feeds  : TechCrunch AI, Ars Technica, MIT Tech Review, OpenAI, Google AI,
                 DeepMind, Anthropic, Meta AI, Microsoft AI, xAI, VentureBeat AI,
                 The Gradient, Import AI, AI Alignment Forum, W&B Blog, HF Blog
  - APIs (free): HackerNews (top AI stories), arXiv (cs.AI/cs.LG/cs.CL/cs.CV),
                 Hugging Face Daily Papers, Papers with Code
  - API (key)  : Product Hunt (trending AI tools)
  - Coming soon: Reddit (r/MachineLearning, r/openai, r/LocalLLaMA, r/artificial)
"""

import feedparser
import requests
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ─── AI-relevancy keyword filter ─────────────────────────────────────────────
AI_KEYWORDS = [
    "artificial intelligence", "machine learning", "deep learning", "neural network",
    "large language model", "llm", "gpt", "claude", "gemini", "llama", "mistral",
    "transformer", "diffusion model", "reinforcement learning", "generative ai",
    "foundation model", "openai", "anthropic", "deepmind", "hugging face",
    "ai model", "ai agent", "multimodal", "nlp", "computer vision", "robotics ai",
    "alignment", "rlhf", "fine-tuning", "inference", "embeddings", "vector",
    "stable diffusion", "midjourney", "dall-e", "sora", "gemma", "phi-",
    "benchmark", "evals", "agi", "superintelligence", "ai safety", "ai research",
    "copilot", "chatgpt", "bard", "perplexity", "cursor", "ai startup",
]

# ─── Product Hunt credentials (loaded from environment) ──────────────────────
import os as _os
PRODUCT_HUNT_TOKEN = _os.getenv("PRODUCT_HUNT_TOKEN", "")

# ─── RSS Feeds ───────────────────────────────────────────────────────────────
AI_TECH_RSS_FEEDS = {
    # Tech news — AI sections
    "techcrunch-ai":     "https://techcrunch.com/category/artificial-intelligence/feed/",
    "arstechnica":       "https://feeds.arstechnica.com/arstechnica/index",
    "mit-tech-review":   "https://www.technologyreview.com/feed/",
    "venturebeat-ai":    "https://venturebeat.com/ai/feed/",
    "wired-ai":          "https://www.wired.com/feed/tag/artificial-intelligence/rss",

    # Company research blogs
    "openai-blog":       "https://openai.com/blog/rss.xml",
    "google-ai-blog":    "https://blog.google/technology/ai/rss/",
    "deepmind-blog":     "https://deepmind.google/blog/rss.xml",
    "anthropic-blog":    "https://www.anthropic.com/rss.xml",
    "meta-ai-blog":      "https://ai.meta.com/blog/rss/",
    "microsoft-ai-blog": "https://blogs.microsoft.com/ai/feed/",
    "xai-blog":          "https://x.ai/blog/feed.xml",
    "huggingface-blog":  "https://huggingface.co/blog/feed.xml",

    # Independent research / community
    "the-gradient":      "https://thegradient.pub/rss/",
    "import-ai":         "https://importai.substack.com/feed",
    "alignment-forum":   "https://www.alignmentforum.org/feed.xml",
    "wandb-blog":        "https://wandb.ai/fully-connected/feed",
    "towards-ds":        "https://towardsdatascience.com/feed",
    "last-week-in-ai":   "https://lastweekin.ai/feed",
}

# Sub-category mapping
SOURCE_SUBCATEGORY = {
    "openai-blog": "Company Blog", "google-ai-blog": "Company Blog",
    "deepmind-blog": "Company Blog", "anthropic-blog": "Company Blog",
    "meta-ai-blog": "Company Blog", "microsoft-ai-blog": "Company Blog",
    "xai-blog": "Company Blog", "huggingface-blog": "Company Blog",
    "techcrunch-ai": "News", "arstechnica": "News", "mit-tech-review": "News",
    "venturebeat-ai": "News", "wired-ai": "News",
    "the-gradient": "Research", "import-ai": "Newsletter",
    "alignment-forum": "Research", "wandb-blog": "Tutorial",
    "towards-ds": "Tutorial", "last-week-in-ai": "Newsletter",
    "hackernews": "Community", "arxiv": "Research Paper",
    "huggingface-papers": "Research Paper", "papers-with-code": "Research Paper",
    "product-hunt": "Product",
}


import re
import html

def strip_html_tags(text: str) -> str:
    if not text:
        return ""
    # Remove HTML tags using a regex
    clean_regex = re.compile('<.*?>')
    cleaned_text = re.sub(clean_regex, '', text)
    # Decode HTML/XML entities (e.g. &amp;, &lt;, &gt;)
    return html.unescape(cleaned_text).strip()


class AiTechCollector:
    """
    Collects AI news & research, filters for AI relevance, summarizes with LLM,
    and saves directly to VerifiedNews with category='AI Tech'.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "UniArc-AIBriefs/1.0 (+https://uniintel.in)"
        })

    # ─── Main entry point ────────────────────────────────────────────────────
    def fetch_and_save(self) -> int:
        """Fetch from all sources, summarize, and save. Returns number saved."""
        logger.info("🤖 AI Briefs Collector — starting fetch from all sources...")
        raw_articles: List[Dict] = []

        # 1. RSS Feeds
        raw_articles.extend(self._fetch_rss_feeds())

        # 2. HackerNews top AI stories
        raw_articles.extend(self._fetch_hackernews())

        # 3. arXiv recent AI papers
        raw_articles.extend(self._fetch_arxiv())

        # 4. Hugging Face Daily Papers
        raw_articles.extend(self._fetch_huggingface_papers())

        # 5. Papers with Code
        raw_articles.extend(self._fetch_papers_with_code())

        # 6. Product Hunt trending AI
        raw_articles.extend(self._fetch_product_hunt())

        # 7. Reddit — placeholder, activated when credentials are provided
        # raw_articles.extend(self._fetch_reddit())

        logger.info(f"🤖 Total raw AI articles collected: {len(raw_articles)}")

        # 8. Filter for AI relevance
        filtered = [a for a in raw_articles if self._is_ai_relevant(a)]
        logger.info(f"🤖 After AI-relevance filter: {len(filtered)} articles")

        # 9. Deduplicate by URL
        seen_urls = set()
        unique = []
        for a in filtered:
            url = a.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(a)
        logger.info(f"🤖 After deduplication: {len(unique)} articles")

        if not unique:
            logger.info("🤖 No new AI articles to save.")
            return 0

        # 10. Summarize with LLM (batched)
        summarized = self._summarize_batch(unique)

        # 11. Save to DB
        saved = self._save_articles(summarized)
        logger.info(f"🤖 AI Briefs saved: {saved} new articles.")
        return saved

    # ─── RSS Feeds ──────────────────────────────────────────────────────────
    def _fetch_rss_feeds(self) -> List[Dict]:
        import concurrent.futures, socket
        all_articles = []
        cutoff = datetime.utcnow() - timedelta(hours=48)

        def _fetch_one(source_id, feed_url):
            try:
                socket.setdefaulttimeout(12)
                feed = feedparser.parse(feed_url)
                articles = []
                for entry in feed.entries:
                    published_at = self._parse_rss_date(entry)
                    if published_at and published_at < cutoff:
                        continue
                    image_url = self._extract_rss_image(entry)
                    content = entry.get("summary", "") or entry.get("description", "") or ""
                    clean_content = strip_html_tags(content)
                    clean_title = strip_html_tags(entry.get("title", ""))
                    articles.append({
                        "source_id": source_id,
                        "source_name": feed.feed.get("title", source_id),
                        "title": clean_title,
                        "url": entry.get("link", ""),
                        "content": clean_content,
                        "image_url": image_url,
                        "published_at": published_at or datetime.utcnow(),
                        "sub_category": SOURCE_SUBCATEGORY.get(source_id, "News"),
                    })
                return articles
            except Exception as e:
                logger.warning(f"RSS fetch failed for {source_id}: {e}")
                return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(_fetch_one, sid, url): sid
                       for sid, url in AI_TECH_RSS_FEEDS.items()}
            for future in concurrent.futures.as_completed(futures):
                all_articles.extend(future.result())

        logger.info(f"RSS: {len(all_articles)} articles fetched")
        return all_articles

    # ─── HackerNews ─────────────────────────────────────────────────────────
    def _fetch_hackernews(self) -> List[Dict]:
        try:
            resp = self.session.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                timeout=10
            )
            story_ids = resp.json()[:80]  # top 80, filter for AI
            articles = []
            for sid in story_ids:
                try:
                    story = self.session.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                        timeout=6
                    ).json()
                    if not story or story.get("type") != "story":
                        continue
                    title = strip_html_tags(story.get("title", ""))
                    url = story.get("url", f"https://news.ycombinator.com/item?id={sid}")
                    text = strip_html_tags(story.get("text", "") or "")
                    published_at = datetime.utcfromtimestamp(story.get("time", time.time()))
                    articles.append({
                        "source_id": "hackernews",
                        "source_name": "Hacker News",
                        "title": title,
                        "url": url,
                        "content": text,
                        "image_url": None,
                        "published_at": published_at,
                        "sub_category": "Community",
                        "score": story.get("score", 0),
                    })
                except Exception:
                    continue
            logger.info(f"HackerNews: {len(articles)} stories fetched")
            return articles
        except Exception as e:
            logger.error(f"HackerNews fetch failed: {e}")
            return []

    # ─── arXiv ──────────────────────────────────────────────────────────────
    def _fetch_arxiv(self) -> List[Dict]:
        try:
            query = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.CV"
            url = (
                f"http://export.arxiv.org/api/query"
                f"?search_query={query}"
                f"&start=0&max_results=25"
                f"&sortBy=submittedDate&sortOrder=descending"
            )
            resp = self.session.get(url, timeout=15)
            root = ET.fromstring(resp.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            articles = []
            for entry in root.findall("atom:entry", ns):
                title = strip_html_tags(entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
                abstract = strip_html_tags(entry.findtext("atom:summary", "", ns) or "").strip()
                link_el = entry.find("atom:link[@rel='alternate']", ns)
                link = link_el.attrib.get("href", "") if link_el is not None else ""
                published_str = entry.findtext("atom:published", "", ns)
                published_at = datetime.utcnow()
                if published_str:
                    try:
                        published_at = datetime.strptime(published_str[:10], "%Y-%m-%d")
                    except Exception:
                        pass
                # Authors
                authors = [
                    a.findtext("atom:name", "", ns)
                    for a in entry.findall("atom:author", ns)
                ]
                categories = [
                    c.attrib.get("term", "")
                    for c in entry.findall("atom:category", ns)
                ]
                articles.append({
                    "source_id": "arxiv",
                    "source_name": "arXiv",
                    "title": title,
                    "url": link,
                    "content": abstract,
                    "image_url": None,
                    "published_at": published_at,
                    "sub_category": "Research Paper",
                    "authors": authors,
                    "tags": categories,
                    "is_research_paper": True,
                })
            logger.info(f"arXiv: {len(articles)} papers fetched")
            return articles
        except Exception as e:
            logger.error(f"arXiv fetch failed: {e}")
            return []

    # ─── Hugging Face Daily Papers ───────────────────────────────────────────
    def _fetch_huggingface_papers(self) -> List[Dict]:
        try:
            resp = self.session.get(
                "https://huggingface.co/api/daily_papers",
                timeout=12
            )
            data = resp.json()
            articles = []
            for item in (data if isinstance(data, list) else []):
                paper = item.get("paper", {})
                title = paper.get("title", "")
                abstract = paper.get("abstract", "")
                arxiv_id = paper.get("id", "")
                url = f"https://huggingface.co/papers/{arxiv_id}" if arxiv_id else ""
                published_str = paper.get("publishedAt", "")
                published_at = datetime.utcnow()
                if published_str:
                    try:
                        published_at = datetime.strptime(published_str[:10], "%Y-%m-%d")
                    except Exception:
                        pass
                thumbnail = item.get("thumbnail", None)
                authors = [a.get("name", "") for a in paper.get("authors", [])]
                articles.append({
                    "source_id": "huggingface-papers",
                    "source_name": "Hugging Face Papers",
                    "title": title,
                    "url": url,
                    "content": abstract,
                    "image_url": thumbnail,
                    "published_at": published_at,
                    "sub_category": "Research Paper",
                    "authors": authors,
                    "is_research_paper": True,
                    "upvotes": item.get("numComments", 0),
                })
            logger.info(f"HuggingFace Papers: {len(articles)} papers fetched")
            return articles
        except Exception as e:
            logger.error(f"Hugging Face papers fetch failed: {e}")
            return []

    # ─── Papers with Code ───────────────────────────────────────────────────
    def _fetch_papers_with_code(self) -> List[Dict]:
        try:
            resp = self.session.get(
                "https://paperswithcode.com/api/v1/papers/?ordering=-published&format=json&page_size=15",
                timeout=12
            )
            data = resp.json()
            articles = []
            for item in data.get("results", []):
                title = item.get("title", "")
                abstract = item.get("abstract", "")
                url = item.get("url_pdf", "") or item.get("paper_url", "")
                published_str = item.get("published", "")
                published_at = datetime.utcnow()
                if published_str:
                    try:
                        published_at = datetime.strptime(published_str[:10], "%Y-%m-%d")
                    except Exception:
                        pass
                authors = item.get("authors", [])
                articles.append({
                    "source_id": "papers-with-code",
                    "source_name": "Papers with Code",
                    "title": title,
                    "url": url,
                    "content": abstract,
                    "image_url": None,
                    "published_at": published_at,
                    "sub_category": "Research Paper",
                    "authors": authors if isinstance(authors, list) else [],
                    "is_research_paper": True,
                })
            logger.info(f"Papers with Code: {len(articles)} papers fetched")
            return articles
        except Exception as e:
            logger.error(f"Papers with Code fetch failed: {e}")
            return []

    # ─── Product Hunt ────────────────────────────────────────────────────────
    def _fetch_product_hunt(self) -> List[Dict]:
        try:
            query = """
            {
              posts(first: 20, topic: "artificial-intelligence", order: VOTES) {
                edges {
                  node {
                    id
                    name
                    tagline
                    description
                    url
                    votesCount
                    thumbnail { imageUrl }
                    createdAt
                    topics { edges { node { name } } }
                  }
                }
              }
            }
            """
            resp = self.session.post(
                "https://api.producthunt.com/v2/api/graphql",
                json={"query": query},
                headers={
                    "Authorization": f"Bearer {PRODUCT_HUNT_TOKEN}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=12,
            )
            data = resp.json()
            articles = []
            edges = data.get("data", {}).get("posts", {}).get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                title = node.get("name", "")
                tagline = node.get("tagline", "")
                description = node.get("description", "") or tagline
                url = node.get("url", "")
                image_url = (node.get("thumbnail") or {}).get("imageUrl")
                created_at_str = node.get("createdAt", "")
                published_at = datetime.utcnow()
                if created_at_str:
                    try:
                        published_at = datetime.strptime(created_at_str[:10], "%Y-%m-%d")
                    except Exception:
                        pass
                articles.append({
                    "source_id": "product-hunt",
                    "source_name": "Product Hunt",
                    "title": f"{title} — {tagline}" if tagline else title,
                    "url": url,
                    "content": description,
                    "image_url": image_url,
                    "published_at": published_at,
                    "sub_category": "Product",
                    "upvotes": node.get("votesCount", 0),
                })
            logger.info(f"Product Hunt: {len(articles)} AI tools fetched")
            return articles
        except Exception as e:
            logger.error(f"Product Hunt fetch failed: {e}")
            return []

    # ─── Reddit (placeholder — activated when credentials are set) ────────────
    def _fetch_reddit(self, client_id: str = "", client_secret: str = "") -> List[Dict]:
        """
        Placeholder for Reddit integration.
        Call this method once the user provides Reddit client_id and client_secret.
        Subreddits: r/MachineLearning, r/openai, r/artificial, r/LocalLLaMA
        """
        if not client_id or not client_secret:
            logger.info("Reddit: credentials not set — skipping")
            return []
        # Will be implemented when Reddit credentials are provided
        return []

    # ─── AI-Relevance Filter ─────────────────────────────────────────────────
    def _is_ai_relevant(self, article: Dict) -> bool:
        """Return True if title or content contains at least one AI keyword."""
        # Research papers and company AI blogs are always relevant
        if article.get("is_research_paper"):
            return True
        if article.get("source_id") in [
            "openai-blog", "google-ai-blog", "deepmind-blog", "anthropic-blog",
            "meta-ai-blog", "microsoft-ai-blog", "xai-blog", "huggingface-blog",
            "huggingface-papers", "papers-with-code", "arxiv",
            "the-gradient", "import-ai", "alignment-forum", "last-week-in-ai",
            "product-hunt",
        ]:
            return True
        text = (
            (article.get("title") or "").lower() + " " +
            (article.get("content") or "").lower()
        )
        return any(kw in text for kw in AI_KEYWORDS)

    # ─── LLM Summarization ──────────────────────────────────────────────────
    def _summarize_batch(self, articles: List[Dict]) -> List[Dict]:
        """
        Summarize articles using the existing LLM key pool.
        - Research papers → 5-6 deep bullet points
        - Regular articles → 3 bullet points
        """
        try:
            from src.analysis.llm_analyzer import LLMAnalyzer
            import asyncio

            analyzer = LLMAnalyzer()
            if not analyzer.openai_keys and not analyzer.groq_keys:
                logger.warning("No LLM keys — saving without summaries")
                for a in articles:
                    a["summary_bullets"] = [a.get("content", "")[:300]]
                return articles

            async def _run_all():
                tasks = [self._summarize_one_async(analyzer, a) for a in articles]
                return await asyncio.gather(*tasks, return_exceptions=True)

            # Run in a fresh event loop in this thread
            loop = asyncio.new_event_loop()
            results = loop.run_until_complete(_run_all())
            loop.close()

            for article, result in zip(articles, results):
                if isinstance(result, list) and result:
                    article["summary_bullets"] = result
                elif not article.get("summary_bullets"):
                    article["summary_bullets"] = [
                        article.get("content", "")[:300] + "..."
                    ]

        except Exception as e:
            logger.error(f"LLM batch summarization failed: {e}")
            for a in articles:
                if not a.get("summary_bullets"):
                    a["summary_bullets"] = [a.get("content", "")[:300] + "..."]

        return articles

    async def _summarize_one_async(self, analyzer, article: Dict) -> List[str]:
        """Call LLM to summarize one article. Returns list of bullet points."""
        import asyncio, openai

        is_paper = article.get("is_research_paper", False)
        title = article.get("title", "")
        content = (article.get("content") or "")[:3000]

        if is_paper:
            prompt = f"""You are an expert AI researcher. Summarize this research paper into exactly 5-6 concise bullet points covering:
1. Objective / Problem
2. Methodology / Approach
3. Key Findings / Results
4. Limitations / Constraints
5. Practical Applications
6. Future Work / Next Steps (if mentioned)

Paper Title: {title}
Abstract: {content}

Respond ONLY as a JSON array of strings. Example: ["• Objective: ...", "• Method: ...", ...]
Do not include any other text."""
        else:
            prompt = f"""Summarize this AI news article into exactly 3 concise bullet points (each max 30 words).

Article Title: {title}
Content: {content}

Respond ONLY as a JSON array of strings. Example: ["• ...", "• ...", "• ..."]
Do not include any other text."""

        provider, idx, key = analyzer._get_best_key(
            provider_preference="groq", preferred_index=0
        )
        if not key:
            return [content[:300] + "..."]

        try:
            async with analyzer.semaphore:
                if provider == "groq":
                    client = openai.AsyncOpenAI(
                        api_key=key,
                        base_url="https://api.groq.com/openai/v1"
                    )
                    model = "llama-3.1-8b-instant"
                else:
                    client = openai.AsyncOpenAI(api_key=key)
                    model = "gpt-4o-mini"

                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=400,
                        temperature=0.3,
                    ),
                    timeout=30.0
                )
                raw = response.choices[0].message.content.strip()
                bullets = json.loads(analyzer._clean_llm_json(raw))
                if isinstance(bullets, list) and all(isinstance(b, str) for b in bullets):
                    return bullets
        except Exception as e:
            logger.warning(f"LLM summarize failed for '{title[:50]}': {e}")

        return [content[:300] + "..."]

    # ─── Database Save ───────────────────────────────────────────────────────
    def _save_articles(self, articles: List[Dict]) -> int:
        """
        Save articles to RawNews + VerifiedNews directly.
        We bypass the normal verifier pipeline so AI Tech articles get
        proper 5-6 bullet summaries and are instantly available in the feed.
        """
        from src.database.models import SessionLocal, RawNews, VerifiedNews
        count = 0

        with SessionLocal() as db:
            try:
                for article in articles:
                    url = article.get("url", "").strip()
                    if not url or len(url) < 10:
                        continue

                    # Skip if already exists in RawNews
                    existing = db.query(RawNews).filter(RawNews.url == url).first()
                    if existing:
                        continue

                    title = (article.get("title") or "").strip()
                    if not title:
                        continue

                    content = article.get("content") or ""
                    published_at = article.get("published_at") or datetime.utcnow()

                    # 1. Create RawNews
                    raw = RawNews(
                        source_id=article.get("source_id", "ai-tech"),
                        source_name=article.get("source_name", "AI Source"),
                        author=", ".join(article.get("authors", []))[:255] if article.get("authors") else None,
                        title=title,
                        description=content[:500],
                        url=url,
                        url_to_image=article.get("image_url"),
                        published_at=published_at,
                        content=content,
                        processed=True,   # Skip normal verifier pipeline
                        is_verified=True,
                        verification_score=0.9,
                        country=None,
                    )
                    db.add(raw)
                    db.flush()  # Get raw.id

                    # 2. Build summary bullets
                    bullets = article.get("summary_bullets") or [content[:300] + "..."]
                    if not isinstance(bullets, list):
                        bullets = [str(bullets)]

                    # 3. Impact score: research papers 8, products 6, news 7
                    sub_cat = article.get("sub_category", "News")
                    if sub_cat == "Research Paper":
                        impact = 8
                    elif sub_cat == "Product":
                        impact = 6
                    elif sub_cat == "Company Blog":
                        impact = 7
                    else:
                        impact = 6

                    # 4. Create VerifiedNews
                    verified = VerifiedNews(
                        raw_news_id=raw.id,
                        title=title,
                        content=content,
                        summary_bullets=bullets,
                        category="AI Tech",
                        sub_category=sub_cat,
                        country=None,
                        credibility_score=0.9,
                        impact_score=impact,
                        sentiment="Positive",
                        why_it_matters=bullets[0] if bullets else "",
                        who_is_affected="AI researchers, developers, and tech enthusiasts",
                        short_term_impact="Immediate advancement in AI capabilities",
                        long_term_impact="Shapes the future of AI development",
                        bias_rating="Neutral",
                        impact_tags=["AI", "Technology", sub_cat],
                        lang="english",
                        published_at=published_at,
                        analysis={
                            "source_id": article.get("source_id"),
                            "is_research_paper": article.get("is_research_paper", False),
                            "authors": article.get("authors", []),
                            "upvotes": article.get("upvotes", 0),
                        },
                        translation_cache={},
                    )
                    db.add(verified)
                    count += 1

                db.commit()
            except Exception as e:
                logger.error(f"AI Tech DB save error: {e}")
                db.rollback()

        return count

    # ─── Helpers ─────────────────────────────────────────────────────────────
    def _parse_rss_date(self, entry) -> Optional[datetime]:
        from dateutil import parser as dateutil_parser
        date_str = entry.get("published") or entry.get("updated") or entry.get("date")
        if not date_str:
            return None
        try:
            dt = dateutil_parser.parse(date_str, tzinfos={
                "EST": -18000, "EDT": -14400, "PST": -28800, "PDT": -25200,
                "IST": 19800, "GMT": 0, "UTC": 0,
            })
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            return dt
        except Exception:
            return None

    def _extract_rss_image(self, entry) -> Optional[str]:
        if "media_content" in entry:
            for m in entry.media_content:
                if m.get("type", "").startswith("image") or m.get("medium") == "image":
                    return m.get("url")
        if "media_thumbnail" in entry:
            return entry.media_thumbnail[0].get("url")
        if "links" in entry:
            for link in entry.links:
                if link.get("rel") == "enclosure" and link.get("type", "").startswith("image"):
                    return link.get("href")
        summary = entry.get("summary", "") or ""
        if '<img' in summary:
            try:
                start = summary.find('src="') + 5
                end = summary.find('"', start)
                if start > 4 and end > start:
                    return summary[start:end]
            except Exception:
                pass
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collector = AiTechCollector()
    count = collector.fetch_and_save()
    print(f"Saved {count} AI Tech articles.")
