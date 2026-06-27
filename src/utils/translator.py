import logging
import random
import json
import asyncio
import time
import httpx
import re
import html
from typing import List, Dict, Any, Union
from openai import AsyncOpenAI
from src.config import settings
from src.database.models import SessionLocal, VerifiedNews

logger = logging.getLogger(__name__)


GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"
HF_NLLB_URL = "https://api-inference.huggingface.co/models/facebook/nllb-200-distilled-600M"

class NewsTranslator:
    def __init__(self):
        # 1. Gather unique non-empty keys from settings pools
        self.openai_keys = list(dict.fromkeys([k for k in settings.OPENAI_API_KEYS if k]))
        self.groq_keys = list(dict.fromkeys([k for k in settings.GROQ_API_KEYS if k]))
        
        # Combined Pool for high-speed rotation
        self.all_keys = self.openai_keys + self.groq_keys
        self.current_key_idx = 0
        
        # 2. Key Status Tracking (To prevent spamming dead/limited keys)
        self._key_status = {}
        
        # REDUCED CONCURRENCY: Higher stability
        self._concurrency_limit = asyncio.Semaphore(5) 
        
        # NLLB Language Mapping
        self.nllb_map = {
            "Telugu": "tel_Telu", "Hindi": "hin_Deva", "Tamil": "tam_Taml",
            "Kannada": "kan_Knda", "Malayalam": "mal_Mlym", "Marathi": "mar_Deva",
            "Bengali": "ben_Beng", "Gujarati": "guj_Gujr", "Arabic": "arb_Arab",
            "Japanese": "jpn_Jpan", "Spanish": "spa_Latn", "French": "fra_Latn",
            "German": "deu_Latn", "Russian": "rus_Cyrl", "Chinese": "zho_Hans",
            "Korean": "kor_Hang", "Portuguese": "por_Latn", "Turkish": "tur_Latn",
            "Punjabi": "pan_Guru", "Italian": "ita_Latn", "Vietnamese": "vie_Latn",
            "Indonesian": "ind_Latn", "Odia": "ory_Orya", "Assamese": "asm_Beng",
            "Dutch": "nld_Latn", "Swedish": "swe_Latn", "Thai": "tha_Thai",
            "Polish": "pol_Latn", "Urdu": "urd_Arab",
            "Ukrainian": "ukr_Cyrl", "Persian": "pes_Arab", "Greek": "ell_Grek",
            "Romanian": "ron_Latn", "Tagalog": "tgl_Latn", "Malay": "zsm_Latn",
            "Hebrew": "heb_Hebr", "Finnish": "fin_Latn", "Hungarian": "hun_Latn",
            "Czech": "ces_Latn"
        }
        
        # Google Translate Language Mapping
        self.google_lang_map = {
            "Telugu": "te", "Hindi": "hi", "Tamil": "ta",
            "Kannada": "kn", "Malayalam": "ml", "Marathi": "mr",
            "Bengali": "bn", "Gujarati": "gu", "Arabic": "ar",
            "Japanese": "ja", "Spanish": "es", "French": "fr",
            "German": "de", "Russian": "ru", "Chinese": "zh",
            "Korean": "ko", "Portuguese": "pt", "Turkish": "tr",
            "Punjabi": "pa", "Italian": "it", "Vietnamese": "vi",
            "Indonesian": "id", "Odia": "or", "Assamese": "as",
            "Dutch": "nl", "Swedish": "sv", "Thai": "th",
            "Polish": "pl", "Urdu": "ur",
            "Ukrainian": "uk", "Persian": "fa", "Greek": "el",
            "Romanian": "ro", "Tagalog": "tl", "Malay": "ms",
            "Hebrew": "he", "Finnish": "fi", "Hungarian": "hu",
            "Czech": "cs"
        }
        
        if not self.all_keys:
            logger.warning("No API keys found for NewsTranslator. Translation will be skipped.")
        else:
            logger.info(f"NewsTranslator initialized with {len(self.all_keys)} keys.")
        
        self._clients: Dict[str, AsyncOpenAI] = {}
        
        # NVIDIA Client setup
        self.nvidia_keys = getattr(settings, "NVIDIA_API_KEYS", [])
        self.nvidia_clients = [
            AsyncOpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=k)
            for k in self.nvidia_keys
        ]
        # Keep single nvidia_client for backward compatibility
        self.nvidia_client = self.nvidia_clients[0] if self.nvidia_clients else None
        
        if self.nvidia_clients:
            logger.info(f"NVIDIA API client initialized with {len(self.nvidia_clients)} keys for translation fallback.")
        else:
            logger.warning("No NVIDIA keys found. NVIDIA translation fallback will be disabled.")
        
        # 3. External Cache (for items with ID 0)
        from pathlib import Path
        self.external_cache_path = settings.DATA_DIR / "external_translations.json"
        self._external_cache = {}
        self._load_external_cache()

    def _load_external_cache(self):
        try:
            if self.external_cache_path.exists():
                with open(self.external_cache_path, "r", encoding="utf-8") as f:
                    self._external_cache = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load external translation cache: {e}")

    def _save_external_cache(self):
        try:
            # Basic pruning: keep it under 5000 items
            if len(self._external_cache) > 5000:
                keys = list(self._external_cache.keys())
                self._external_cache = {k: self._external_cache[k] for k in keys[-3000:]}
                
            with open(self.external_cache_path, "w", encoding="utf-8") as f:
                json.dump(self._external_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save external translation cache: {e}")

    def is_already_in_lang(self, text: str, target_lang: str) -> bool:
        if not text or not target_lang:
            return False
            
        lang_unicode_ranges = {
            "Hindi": r"[\u0900-\u097F]",
            "Telugu": r"[\u0c00-\u0c7F]",
            "Tamil": r"[\u0b80-\u0bFF]",
            "Kannada": r"[\u0c80-\u0cFF]",
            "Malayalam": r"[\u0d00-\u0d7F]",
            "Bengali": r"[\u0980-\u09FF]",
            "Gujarati": r"[\u0a80-\u0aFF]",
            "Arabic": r"[\u0600-\u06FF]",
            "Japanese": r"[\u3040-\u30FF\u31F0-\u31FF\u4E00-\u9FFF]",
            "Chinese": r"[\u4E00-\u9FFF]",
            "Korean": r"[\uAC00-\uD7AF\u1100-\u11FF]",
            "Russian": r"[\u0400-\u04FF]",
            "Punjabi": r"[\u0A00-\u0A7F]",
            "Odia": r"[\u0B00-\u0B7F]",
            "Assamese": r"[\u0980-\u09FF]",
            "Thai": r"[\u0E00-\u0E7F]",
            "Urdu": r"[\u0600-\u06FF]"
        }
        
        pattern = lang_unicode_ranges.get(target_lang.capitalize()) or lang_unicode_ranges.get(target_lang)
        if not pattern:
            return False
            
        # If the text has any characters matching the target language's script, check the count
        matches = re.findall(pattern, text)
        if not matches:
            return False
            
        # If more than 3 characters (or 5% of non-whitespace characters) match the script, skip translation
        non_ws_len = len([c for c in text if not c.isspace()])
        if non_ws_len == 0:
            return False
        percent_match = len(matches) / non_ws_len
        
        return len(matches) > 3 or percent_match > 0.05

    async def translate_nvidia(self, text: str, target_lang: str, attempts: int = 3) -> str:
        """
        Layer 3: NVIDIA API Catalog translation layer (High-speed, premium quality).
        Used as fallback/primary high-speed translation layer.
        """
        if not text or not target_lang:
            return text
            
        if not self.nvidia_clients:
            return text
            
        for i in range(attempts):
            client = self.nvidia_clients[i % len(self.nvidia_clients)]
            try:
                response = await client.chat.completions.create(
                    model="meta/llama-3.3-70b-instruct",
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are a master news journalist and professional translator. Translate the text to {target_lang}. RETURN ONLY THE TRANSLATED TEXT. DO NOT explain, do not add introductory text, do not add quotes, just return the translated text."
                        },
                        {"role": "user", "content": text}
                    ],
                    temperature=0.2,
                    top_p=0.7,
                    max_tokens=1024
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"NVIDIA translation attempt {i+1} failed with client index {i % len(self.nvidia_clients)}: {e}")
                if i < attempts - 1:
                    await asyncio.sleep(1)
        return text

    async def translate_microsoft(self, text: str, target_lang: str, attempts: int = 3) -> str:
        """
        Layer 3.5: Microsoft Translator API (Cognitive Services translation layer).
        High-speed, premium quality fallback.
        """
        if not text or not target_lang:
            return text
            
        key = getattr(settings, "MICROSOFT_TRANSLATOR_KEY", None)
        region = getattr(settings, "MICROSOFT_TRANSLATOR_REGION", "eastasia")
        endpoint = getattr(settings, "MICROSOFT_TRANSLATOR_ENDPOINT", "https://api.cognitive.microsofttranslator.com/")
        
        if not key:
            return text

        ms_code = self.google_lang_map.get(target_lang.capitalize()) or self.google_lang_map.get(target_lang)
        if not ms_code:
            return text

        url = f"{endpoint.rstrip('/')}/translate"
        params = {
            'api-version': '3.0',
            'to': ms_code
        }
        headers = {
            'Ocp-Apim-Subscription-Key': key,
            'Ocp-Apim-Subscription-Region': region,
            'Content-Type': 'application/json'
        }
        body = [{'text': text}]

        for i in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(url, params=params, headers=headers, json=body)
                    if response.status_code == 200:
                        result = response.json()
                        if result and isinstance(result, list) and len(result) > 0:
                            trans_list = result[0].get("translations", [])
                            if trans_list:
                                return trans_list[0].get("text", text)
                    else:
                        logger.warning(f"Microsoft Translator API returned error {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Microsoft translation attempt {i+1} failed: {e}")
                if i < attempts - 1:
                    await asyncio.sleep(1)
        return text

    async def verify_all_keys(self) -> Dict[str, Any]:
        """
        Hardcore check: verifies every OpenAI and Groq key in the pool.
        Returns a detailed report of active/dead keys.
        """
        logger.info("Starting hardcore key health verification...")
        results = {"active": [], "dead": [], "limited": []}
        
        async def check_single_key(key):
            client, provider = self._get_client_by_key(key)
            model = "gpt-4o-mini" if provider == "OpenAI" else GROQ_MODEL
            try:
                # Minimum prompt to save tokens
                await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=5,
                    timeout=10
                )
                self._key_status[key] = {"status": "active", "retry_after": 0}
                return key, provider, "active"
            except Exception as e:
                error_msg = str(e).lower()
                is_rate = any(word in error_msg for word in ["429", "rate limit", "rate_limit", "throttle", "too many requests"]) and "insufficient_quota" not in error_msg and "quota exceeded" not in error_msg
                is_quota = not is_rate and any(word in error_msg for word in ["quota", "insufficient", "spend", "invalid", "deactivated", "disabled", "revoked", "billing"])
                
                status = "dead" if is_quota else ("limited" if is_rate else "error")
                self._mark_key_limited(key, is_dead=(status == "dead"))
                return key, provider, status

        tasks = [check_single_key(k) for k in self.all_keys]
        checks = await asyncio.gather(*tasks)
        
        for key, provider, status in checks:
            short_key = f"{key[:6]}...{key[-4:]}"
            if status == "active":
                results["active"].append(f"{provider}: {short_key}")
            elif status == "dead":
                results["dead"].append(f"{provider}: {short_key}")
            else:
                results["limited"].append(f"{provider}: {short_key}")
        
        logger.info(f"Verification complete: {len(results['active'])} active, {len(results['dead'])} dead, {len(results['limited'])} limited.")
        return results

    async def translate_nllb(self, text: str, target_lang: str, attempts: int = 3) -> str:
        """
        Layer 3: Emergency Fallback using NLLB via Hugging Face.
        Zero cost, infinite availability (within rate limits).
        Enhanced with robust retry logic and error handling.
        """
        if not text or not target_lang:
            return text
            
        if not settings.HUGGINGFACE_API_KEY:
            return text
            
        nllb_code = self.nllb_map.get(target_lang.capitalize()) or self.nllb_map.get(target_lang)
        if not nllb_code:
            return text

        headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"}
        payload = {
            "inputs": text,
            "parameters": {"src_lang": "eng_Latn", "tgt_lang": nllb_code}
        }

        for i in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=45) as client:
                    response = await client.post(HF_NLLB_URL, headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if isinstance(result, list) and len(result) > 0:
                            return result[0].get("translation_text", text)
                        return text
                    
                    if response.status_code == 503: # Model loading
                        wait_time = (i + 1) * 3
                        logger.info(f"NLLB model loading (503). Waiting {wait_time}s before retry {i+1}/{attempts}...")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    if response.status_code == 429: # Rate limit
                        wait_time = (i + 1) * 5
                        logger.warning(f"NLLB rate limited (429). Waiting {wait_time}s before retry {i+1}/{attempts}...")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    logger.warning(f"NLLB failed with status {response.status_code}: {response.text}")
                    break # Don't retry for other errors (e.g. 400, 401)
                    
            except Exception as e:
                logger.error(f"NLLB attempt {i+1} failed with error: {e}")
                if i < attempts - 1:
                    await asyncio.sleep(2)
                continue
        
        return text

    def _get_best_key(self):
        """Selects the next available key from the rotation pool, prioritizing premium keys but using random offsets to avoid parallel collisions."""
        now = time.time()
        
        premium_openai = [settings.OPENAI_KEY_1, settings.OPENAI_KEY_2, settings.OPENAI_KEY_3]
        premium_groq = [settings.GROQ_KEY_1, settings.GROQ_KEY_2]
        
        all_others = [k for k in self.all_keys if k not in premium_openai and k not in premium_groq]
        priority_queue = [k for k in premium_openai if k] + [k for k in premium_groq if k] + all_others
        
        num_keys = len(priority_queue)
        if num_keys == 0:
            return None, None
            
        # Start scanning from a random offset to prevent concurrent requests from picking the same key
        start_idx = random.randint(0, num_keys - 1)
        for i in range(num_keys):
            idx = (start_idx + i) % num_keys
            key = priority_queue[idx]
            status = self._key_status.get(key, {"status": "active", "retry_after": 0})
            if status["status"] == "dead": continue
            if status["status"] == "cooled_down":
                if now < status["retry_after"]: continue
                else: self._key_status[key] = {"status": "active", "retry_after": 0}
            
            return key, idx
        return None, None

    def _clean_json(self, text_content):
        """Search for and extract valid JSON from a mixed-text response with high recovery."""
        if not text_content: return None
        try:
            clean = text_content.strip()
            # Remove Markdown code blocks if present
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0].strip()
            elif "```" in clean:
                clean = clean.split("```")[1].strip()
            
            # Find the first { and last }
            start = clean.find('{')
            end = clean.rfind('}')
            if start != -1 and end != -1:
                clean = clean[start:end+1]
            
            # Remove trailing commas before closing braces/brackets
            import re
            clean = re.sub(r',\s*([\]}])', r'\1', clean)
            
            # Handle common LLM escape character issues
            clean = clean.replace('\\"', '"').replace('\\n', ' ')
            # Fix double quotes inside strings (basic attempt)
            # clean = re.sub(r'(?<![:\[,])"(?![:,\]])', "'", clean) 

            return json.loads(clean)
        except Exception as e:
            # Layer 2: Attempt even more aggressive cleaning if Layer 1 fails
            try:
                # Replace newlines in strings which break json.loads
                clean = re.sub(r'\n', ' ', clean)
                return json.loads(clean)
            except:
                logger.warning(f"JSON extraction failed: {e}. Raw: {text_content[:150]}...")
                return None

    def _mark_key_limited(self, key, is_dead=False):
        if is_dead:
            self._key_status[key] = {"status": "dead", "retry_after": 0}
        else:
            self._key_status[key] = {"status": "cooled_down", "retry_after": time.time() + 30}

    def _get_client_by_key(self, key):
        if not key: return None, "None"
        is_groq = key.startswith("gsk_")
        if key not in self._clients:
            if is_groq:
                self._clients[key] = AsyncOpenAI(api_key=key, base_url=GROQ_BASE_URL, max_retries=0)
            else:
                self._clients[key] = AsyncOpenAI(api_key=key, base_url="https://api.openai.com/v1", max_retries=0)
        
        provider = "Groq" if is_groq else "OpenAI"
        return self._clients[key], provider

    async def translate_text(self, text: str, target_lang: str) -> str:
        """Translate a single piece of text to target_lang with 4-layer failover."""
        if not text or not target_lang or target_lang.lower() == 'english':
            return text

        # Task 3: Language Detection Skip
        if self.is_already_in_lang(text, target_lang):
            logger.info(f"Skipping translation: text already in target language '{target_lang}'")
            return text
        
        # 1. Prepare candidate pools (Layer 1 & 2: OpenAI & Groq)
        attempt_pools = []
        if self.openai_keys: attempt_pools.append(("openai", self.openai_keys))
        if self.groq_keys: attempt_pools.append(("groq", self.groq_keys))

        for provider, keys in attempt_pools:
            shuffled_keys = list(keys)
            random.shuffle(shuffled_keys)
            
            for i, key in enumerate(shuffled_keys):
                status_info = self._key_status.get(key, {"status": "active"})
                if status_info["status"] == "dead": continue
                if status_info["status"] == "cooled_down" and time.time() < status_info.get("retry_after", 0):
                    continue
                
                try:
                    client, _ = self._get_client_by_key(key)
                    model = "gpt-4o-mini" if provider == "openai" else GROQ_MODEL
                    
                    response = await client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": f"You are a master news journalist and professional translator. Translate to {target_lang}. RETURN ONLY THE TRANSLATED TEXT."
                            },
                            {"role": "user", "content": text}
                        ],
                        temperature=0.1,
                        timeout=30 # Increased for stability
                    )
                    return response.choices[0].message.content.strip()
                except Exception as e:
                    error_msg = str(e).lower()
                    is_rate = any(word in error_msg for word in ["429", "rate limit", "rate_limit", "throttle", "too many requests"]) and "insufficient_quota" not in error_msg and "quota exceeded" not in error_msg
                    is_quota = not is_rate and any(word in error_msg for word in ["quota", "insufficient", "spend", "invalid", "deactivated", "disabled", "revoked", "billing"])
                    if is_quota or is_rate:
                        self._mark_key_limited(key, is_dead=is_quota)
                    continue

        # 2. Layer 3: Microsoft Translator API (Cognitive Services fallback)
        try:
            logger.info(f"LLM layers failed. Attempting Microsoft translation for target lang: {target_lang}")
            translated = await self.translate_microsoft(text, target_lang)
            if translated and translated != text:
                return translated
        except Exception as me:
            logger.warning(f"Microsoft translation layer failed: {me}")

        # 2.5 Layer 3.5: NVIDIA API (High-performance fallback)
        try:
            logger.info(f"Microsoft layer failed. Attempting NVIDIA translation for target lang: {target_lang}")
            translated = await self.translate_nvidia(text, target_lang)
            if translated and translated != text:
                return translated
        except Exception as ne:
            logger.warning(f"NVIDIA translation layer failed: {ne}")

        # 3. Layer 4: NLLB (Final emergency fallback)
        if target_lang in self.nllb_map:
            logger.warning(f"LLM, Microsoft & NVIDIA layers failed for {target_lang}. Using NLLB fallback.")
            return await self.translate_nllb(text, target_lang)
        
        return text

    async def translate_stories(self, stories: List[Dict[str, Any]], target_lang: str) -> List[Dict[str, Any]]:
        """Translate multiple stories with parallel execution and DB caching."""
        if not stories or not target_lang or target_lang.lower() == 'english':
            return stories

        target_lang = target_lang.strip().capitalize()
        translated_stories = json.loads(json.dumps(stories))
        node_data = {"stories": translated_stories}
        await self.translate_node_bulk(node_data, target_lang)
        return node_data.get("stories", translated_stories)

    async def translate_node_bulk(self, node_data: Dict[str, Any], target_lang: str) -> Dict[str, Any]:
        """Translate entire node dashboard with DB caching and NLLB fallback."""
        if not target_lang or target_lang.lower() == 'english':
            return node_data

        stories = node_data.get("stories", [])
        if not stories:
            return node_data

        def _load_cache_sync():
            db = SessionLocal()
            u_indices = []
            try:
                # Batch retrieve all articles in a single query
                article_ids = []
                for story in stories:
                    art_id = story.get("id")
                    if art_id and str(art_id).isdigit():
                        article_ids.append(int(art_id))
                
                articles_map = {}
                if article_ids:
                    db_articles = db.query(VerifiedNews).filter(VerifiedNews.id.in_(article_ids)).all()
                    articles_map = {a.id: a for a in db_articles}

                for idx, story in enumerate(stories):
                    # Task 3: Language Detection Skip
                    if self.is_already_in_lang(story.get("title", ""), target_lang):
                        story.update({
                            "is_translated": True,
                            "is_cached": True
                        })
                        continue
                    article_id = story.get("id")
                    if article_id and str(article_id).isdigit():
                        article = articles_map.get(int(article_id))
                        if article and article.translation_cache:
                            cache = article.translation_cache
                            if isinstance(cache, str):
                                try: cache = json.loads(cache)
                                except: cache = {}
                            
                            if target_lang in cache:
                                cached_val = cache[target_lang]
                                cached_title = cached_val.get("title") or story.get("title") or story.get("headline")
                                cached_bullets = cached_val.get("bullets") or story.get("bullets") or story.get("summary_bullets") or []
                                cached_why = cached_val.get("why") or story.get("why") or story.get("why_it_matters") or story.get("summary") or ""
                                cached_affected = cached_val.get("affected") or story.get("affected") or story.get("who_is_affected") or ""
                                
                                story.update({
                                    "title": cached_title,
                                    "headline": cached_title,
                                    "bullets": cached_bullets,
                                    "summary_bullets": cached_bullets,
                                    "why": cached_why,
                                    "why_it_matters": cached_why,
                                    "summary": cached_why,
                                    "affected": cached_affected,
                                    "who_is_affected": cached_affected,
                                    "is_cached": True,
                                    "is_translated": True
                                })
                                continue
                        
                    # 2. Check External Cache (URL-based) if ID is 0
                    if str(article_id) == "0" or not article_id:
                        url = story.get("url")
                        cache_key = f"{url}_{target_lang}" if url else None
                        if cache_key and cache_key in self._external_cache:
                            cached_val = self._external_cache[cache_key]
                            cached_title = cached_val.get("t") or story.get("title") or story.get("headline")
                            cached_bullets = cached_val.get("b") or story.get("bullets") or story.get("summary_bullets") or []
                            cached_why = cached_val.get("w") or story.get("why") or story.get("why_it_matters") or story.get("summary") or ""
                            cached_affected = cached_val.get("a") or story.get("affected") or story.get("who_is_affected") or ""
                            
                            story.update({
                                "title": cached_title,
                                "headline": cached_title,
                                "bullets": cached_bullets,
                                "summary_bullets": cached_bullets,
                                "why": cached_why,
                                "why_it_matters": cached_why,
                                "summary": cached_why,
                                "affected": cached_affected,
                                "who_is_affected": cached_affected,
                                "is_cached": True,
                                "is_translated": True
                            })
                            continue
                    u_indices.append(idx)
            finally:
                db.close()
            return u_indices
        
        try:
            untranslated_indices = await asyncio.to_thread(_load_cache_sync)
            if not untranslated_indices:
                return node_data

            to_translate_full = [stories[i] for i in untranslated_indices]
            batch_size = 4
            batches = [to_translate_full[i:i + batch_size] for i in range(0, len(to_translate_full), batch_size)]
            
            async def translate_batch(batch_items, b_idx):
                async with self._concurrency_limit:
                    key, k_idx = self._get_best_key()
                    if not key:
                        return []
                    client, provider = self._get_client_by_key(key)
                    await asyncio.sleep(b_idx * 0.4) 
                
                articles_text = ""
                for idx, story in enumerate(batch_items, 1):
                    bullets = story.get("bullets") or story.get("summary_bullets") or []
                    if isinstance(bullets, str):
                        bullets = [bullets]
                    why = story.get("why") or story.get("why_it_matters") or story.get("summary") or "N/A"
                    affected = story.get("affected") or story.get("who_is_affected") or "N/A"
                    title = story.get("title") or story.get("headline") or ""
                    articles_text += f"ID: {story.get('id', idx)}\nT: {title}\nB: {' | '.join(bullets)}\nW: {why}\nA: {affected}\n---\n"

                max_attempts = 3 # Fast failover for batches
                for attempt in range(max_attempts):
                    try:
                        batch_model = GROQ_MODEL if provider == "Groq" else "gpt-4o-mini"
                        response = await client.chat.completions.create(
                            model=batch_model,
                            messages=[
                                {"role": "system", "content": f"You are a professional news journalist and master translator. Translate the following news articles to {target_lang} using high-quality regional phrasing. Return ONLY a valid JSON object with the structure: {{\"translated\": [ {{ \"id\": \"id\", \"t\": \"title\", \"b\": [\"bullet\"], \"w\": \"why\", \"a\": \"affected\" }} ]}}"},
                                {"role": "user", "content": f"Translate these to {target_lang}:\n{articles_text}"}
                            ],
                            temperature=0.1,
                            timeout=60 # High timeout for batch stability
                        )
                        raw_result = self._clean_json(response.choices[0].message.content.strip())
                        if raw_result and raw_result.get("translated"):
                            logger.info(f"Successfully translated {len(raw_result.get('translated'))} items to {target_lang}")
                            return raw_result.get("translated")
                        else:
                            logger.warning(f"Translation JSON parse failed for {target_lang}. Response was not in expected format.")
                            # Treat JSON parse error as a minor error, trigger rotate
                            self._mark_key_limited(key, is_dead=False)

                    except Exception as e:
                        error_msg = str(e).lower()
                        is_rate = any(word in error_msg for word in ["429", "rate limit", "rate_limit", "throttle", "too many requests"]) and "insufficient_quota" not in error_msg and "quota exceeded" not in error_msg
                        is_quota = not is_rate and any(word in error_msg for word in ["quota", "insufficient", "spend", "invalid", "deactivated", "disabled", "revoked", "billing"])
                        self._mark_key_limited(key, is_dead=is_quota)
                        logger.warning(f"Batch translation failed on key {key[:8]}... (attempt {attempt+1}/{max_attempts}): {e}. Rotating...")

                    # Rotate key for the next attempt
                    key, k_idx = self._get_best_key()
                    if not key:
                        break
                    client, provider = self._get_client_by_key(key)
                
                # BATCH FAILBACK: Parallel single-item translation fallback
                async def translate_item_safe(item):
                    try:
                        title = item.get("title") or item.get("headline")
                        bullets = item.get("bullets") or item.get("summary_bullets") or []
                        if isinstance(bullets, str):
                            bullets = [bullets]
                        why = item.get("why") or item.get("why_it_matters") or item.get("summary")
                        affected = item.get("affected") or item.get("who_is_affected")
                        
                        t_task = self.translate_text(title, target_lang)
                        b_tasks = [self.translate_text(b, target_lang) for b in bullets]
                        w_task = self.translate_text(why, target_lang)
                        a_task = self.translate_text(affected, target_lang)
                        
                        t, b, w, a = await asyncio.gather(t_task, asyncio.gather(*b_tasks), w_task, a_task)
                        return {"id": item.get("id"), "t": t, "b": b, "w": w, "a": a}
                    except Exception as e:
                        logger.error(f"Single item fallback failed: {e}")
                        return {"id": item.get("id"), "t": item.get("title") or item.get("headline"), "b": item.get("bullets") or item.get("summary_bullets") or [], "w": item.get("why") or item.get("why_it_matters") or item.get("summary"), "a": item.get("affected") or item.get("who_is_affected")}

                return await asyncio.gather(*[translate_item_safe(item) for item in batch_items])

            batch_results = await asyncio.gather(*[translate_batch(b, i) for i, b in enumerate(batches)])
            all_translated = [tr for res in batch_results for tr in res]

            def _save_cache_sync():
                db = SessionLocal()
                try:
                    trans_map = {str(tr.get("id")): tr for tr in all_translated}
                    for idx in untranslated_indices:
                        orig = stories[idx]
                        tr = trans_map.get(str(orig.get("id")))
                        if not tr: continue
                        
                        cached_title = tr.get("t")
                        cached_bullets = tr.get("b")
                        cached_why = tr.get("w")
                        cached_affected = tr.get("a")

                        orig.update({
                            "title": cached_title, "headline": cached_title, "bullets": cached_bullets, "summary_bullets": cached_bullets,
                            "why": cached_why, "why_it_matters": cached_why, "summary": cached_why,
                            "affected": cached_affected, "who_is_affected": cached_affected,
                            "is_translated": True
                        })

                        article = db.query(VerifiedNews).filter(VerifiedNews.id == int(orig["id"])).first()
                        if article:
                            cache = article.translation_cache or {}
                            cache[target_lang] = {
                                "title": cached_title, "bullets": cached_bullets,
                                "why": cached_why, "affected": cached_affected
                            }
                            article.translation_cache = cache
                            db.commit()
                        
                        # 2. Save External Cache
                        if str(orig.get("id")) == "0":
                            url = orig.get("url")
                            if url:
                                cache_key = f"{url}_{target_lang}"
                                self._external_cache[cache_key] = {
                                    "t": tr.get("t"), "b": tr.get("b"), 
                                    "w": tr.get("w"), "a": tr.get("a")
                                }
                    
                    self._save_external_cache()
                finally:
                    db.close()

            await asyncio.to_thread(_save_cache_sync)
            return node_data
        except Exception as e:
            logger.error(f"Bulk translation failed: {e}")
            return node_data

    async def _do_translate(self, items: List[Dict[str, str]], target_lang: str, node_title: str = "") -> Dict[str, Any]:
        if not items or not target_lang or target_lang.lower() == 'english':
            return {"translated_stories": items, "node_title": node_title}
        try:
            translated = await self.translate_stories(items, target_lang)
            trans_title = await self.translate_text(node_title, target_lang) if node_title else node_title
            return {"translated_stories": translated, "node_title": trans_title}
        except Exception as e:
            return {"translated_stories": items, "node_title": node_title}
