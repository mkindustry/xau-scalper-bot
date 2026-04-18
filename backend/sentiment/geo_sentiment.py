"""
GeoSentimentEngine — Surveillance news géopolitique + macro en temps réel
Sources : NewsAPI.org (actualités) + Finnhub (news financières)
Scoring : Claude Haiku → impact sur XAU/USD (bullish / bearish / neutre + intensité)

Logique d'impact sur XAU :
  BULLISH XAU  → guerres, crises bancaires, récession, Fed dovish surprise, inflation > attentes
  BEARISH XAU  → paix, hausse taux surprise, dollar fort, risk-on rally, inflation < attentes
"""

import os
import asyncio
import logging
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

log = logging.getLogger("sentiment")

# ─── TOPICS PRIORITAIRES XAU ────────────────────────────────────────────────
XAU_BULLISH_KEYWORDS = [
    "war", "conflict", "invasion", "attack", "missile", "nuclear", "sanction",
    "bank collapse", "bank run", "banking crisis", "SVB", "recession", "default",
    "sovereign debt", "Fed pivot", "rate cut", "QE", "quantitative easing",
    "inflation surge", "CPI beat", "hyperinflation", "dollar weakness",
    "geopolitical", "terror", "coup", "escalation", "Gaza", "Ukraine", "Taiwan",
    "safe haven", "gold demand", "central bank gold", "de-dollarization",
    "BRICS gold", "Fed pause", "Powell dovish"
]

XAU_BEARISH_KEYWORDS = [
    "ceasefire", "peace deal", "rate hike", "hawkish", "Fed aggressive",
    "inflation cooling", "CPI miss", "dollar surge", "risk-on", "bull market",
    "soft landing", "disinflation", "Fed tighten", "yield surge", "bond selloff",
    "strong jobs", "NFP beat", "economic recovery", "gold selloff", "gold outflow"
]

SEARCH_QUERIES = [
    # Géopolitique
    "war conflict nuclear geopolitical crisis",
    "Fed Federal Reserve interest rate decision Powell",
    "gold XAU safe haven demand",
    "banking crisis bank collapse financial",
    "inflation CPI PPI Federal Reserve",
    "Ukraine Russia Middle East Taiwan conflict",
    "BRICS de-dollarization central bank gold",
    # Macro
    "US recession GDP economic outlook",
    "dollar DXY currency crisis",
    "oil price energy supply shock",
]


class GeoSentimentEngine:
    def __init__(self):
        self.news_api_key    = os.getenv("NEWS_API_KEY", "")
        self.finnhub_key     = os.getenv("FINNHUB_API_KEY", "")
        self.anthropic_key   = os.getenv("ANTHROPIC_API_KEY", "")
        self.cache: List[Dict] = []
        self.last_fetch: Optional[datetime] = None
        self.fetch_interval  = 300  # 5 minutes

    # ─── FETCH PIPELINE ─────────────────────────────────────────────────────

    async def fetch_all(self) -> List[Dict]:
        """Aggregate news from all sources, deduplicate, return raw list"""
        tasks = [
            self._fetch_newsapi(),
            self._fetch_finnhub(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_news = []
        for r in results:
            if isinstance(r, list):
                all_news.extend(r)

        # Deduplicate by title similarity
        seen = set()
        unique = []
        for n in all_news:
            key = n["title"][:60].lower()
            if key not in seen:
                seen.add(key)
                unique.append(n)

        # Sort by published desc, keep top 40
        unique.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        return unique[:40]

    async def _fetch_newsapi(self) -> List[Dict]:
        if not self.news_api_key:
            return []
        results = []
        # NewsAPI free tier: 100 req/day → one broad query
        query = "gold OR federal reserve OR war OR inflation OR banking crisis OR geopolitical"
        url   = "https://newsapi.org/v2/everything"
        params = {
            "q":        query,
            "language": "en",
            "sortBy":   "publishedAt",
            "pageSize": 30,
            "from":     (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S"),
            "apiKey":   self.news_api_key,
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, params=params, timeout=10) as r:
                    data = await r.json()
            for art in data.get("articles", []):
                results.append({
                    "source":       "NewsAPI",
                    "title":        art.get("title", ""),
                    "description":  art.get("description", ""),
                    "url":          art.get("url", ""),
                    "published_at": art.get("publishedAt", ""),
                    "source_name":  art.get("source", {}).get("name", ""),
                })
        except Exception as e:
            log.error(f"NewsAPI error: {e}")
        return results

    async def _fetch_finnhub(self) -> List[Dict]:
        if not self.finnhub_key:
            return []
        results = []
        url = "https://finnhub.io/api/v1/news"
        params = {"category": "general", "token": self.finnhub_key, "minId": 0}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, params=params, timeout=10) as r:
                    articles = await r.json()
            for art in articles[:20]:
                results.append({
                    "source":       "Finnhub",
                    "title":        art.get("headline", ""),
                    "description":  art.get("summary", ""),
                    "url":          art.get("url", ""),
                    "published_at": datetime.fromtimestamp(art.get("datetime", 0), tz=timezone.utc).isoformat(),
                    "source_name":  art.get("source", "Finnhub"),
                })
        except Exception as e:
            log.error(f"Finnhub news error: {e}")
        return results

    # ─── SCORING ────────────────────────────────────────────────────────────

    async def score_batch(self, articles: List[Dict]) -> List[Dict]:
        """Score each article via Claude Haiku — batched to minimize API calls"""
        if not articles:
            return []
        if not self.anthropic_key:
            return [self._fallback_score(a) for a in articles]

        # Build batch prompt (all articles in one call)
        articles_text = "\n".join([
            f"[{i}] {a['title']} — {a.get('description','')[:120]}"
            for i, a in enumerate(articles)
        ])

        prompt = f"""Tu es un analyste macro spécialisé XAU/USD (or). Pour chaque news ci-dessous, évalue son impact sur le prix de l'or.

Réponds UNIQUEMENT en JSON valide, un objet par news, avec ce format exact :
[
  {{"idx":0,"impact":"BULLISH"|"BEARISH"|"NEUTRAL","intensity":1|2|3,"reason":"<10 mots max>","urgency":"HIGH"|"MEDIUM"|"LOW"}},
  ...
]

Intensité : 1=faible, 2=modérée, 3=forte (mover significatif)
Urgency HIGH = peut mover le marché dans les 2h

RÈGLES IMPACT XAU :
- Guerres/conflits/escalade → BULLISH 2-3
- Crise bancaire/dette souveraine → BULLISH 3
- Fed dovish/pause/cut → BULLISH 2-3
- Inflation > attentes → BULLISH 2
- Dollar fort / hawkish Fed → BEARISH 2
- Risk-on / équités en hausse → BEARISH 1
- Ceasefire / paix → BEARISH 2
- Inflation < attentes → BEARISH 2

NEWS :
{articles_text}

JSON uniquement, pas d'autre texte :"""

        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key":         self.anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type":      "application/json",
                    },
                    json={
                        "model":      "claude-haiku-4-5-20251001",
                        "max_tokens": 2000,
                        "messages":   [{"role": "user", "content": prompt}],
                    },
                    timeout=20,
                ) as r:
                    resp = await r.json()

            raw = resp["content"][0]["text"].strip()
            scores = json.loads(raw)

            # Merge scores into articles
            scored = []
            for a in articles:
                a_copy = dict(a)
                a_copy["impact"]    = "NEUTRAL"
                a_copy["intensity"] = 1
                a_copy["reason"]    = ""
                a_copy["urgency"]   = "LOW"
                scored.append(a_copy)

            for s_item in scores:
                idx = s_item.get("idx", -1)
                if 0 <= idx < len(scored):
                    scored[idx]["impact"]    = s_item.get("impact",    "NEUTRAL")
                    scored[idx]["intensity"] = s_item.get("intensity", 1)
                    scored[idx]["reason"]    = s_item.get("reason",    "")
                    scored[idx]["urgency"]   = s_item.get("urgency",   "LOW")

            return scored

        except Exception as e:
            log.error(f"Claude scoring failed: {e}")
            return [self._fallback_score(a) for a in articles]

    def _fallback_score(self, article: Dict) -> Dict:
        """Rule-based fallback scoring"""
        title = (article.get("title", "") + " " + article.get("description", "")).lower()
        bull = sum(1 for kw in XAU_BULLISH_KEYWORDS if kw.lower() in title)
        bear = sum(1 for kw in XAU_BEARISH_KEYWORDS if kw.lower() in title)

        if bull > bear:
            impact = "BULLISH"
            intensity = min(bull, 3)
        elif bear > bull:
            impact = "BEARISH"
            intensity = min(bear, 3)
        else:
            impact = "NEUTRAL"
            intensity = 1

        return {
            **article,
            "impact":    impact,
            "intensity": intensity,
            "reason":    "keyword-based",
            "urgency":   "MEDIUM" if intensity >= 2 else "LOW",
        }

    # ─── MAIN PIPELINE ──────────────────────────────────────────────────────

    async def run(self) -> Dict:
        """Full pipeline: fetch → score → aggregate sentiment → return"""
        articles = await self.fetch_all()
        scored   = await self.score_batch(articles)
        self.cache = scored
        self.last_fetch = datetime.now(timezone.utc)

        # Aggregate market bias
        bull_score = sum(a["intensity"] for a in scored if a["impact"] == "BULLISH")
        bear_score = sum(a["intensity"] for a in scored if a["impact"] == "BEARISH")
        high_urgency = [a for a in scored if a.get("urgency") == "HIGH"]

        total = bull_score + bear_score or 1
        bull_pct = round(bull_score / total * 100)
        bear_pct = round(bear_score / total * 100)

        if bull_pct >= 60:
            overall = "BULLISH"
        elif bear_pct >= 60:
            overall = "BEARISH"
        else:
            overall = "MIXED"

        return {
            "overall_bias":    overall,
            "bull_score":      bull_score,
            "bear_score":      bear_score,
            "bull_pct":        bull_pct,
            "bear_pct":        bear_pct,
            "high_urgency":    high_urgency,
            "total_articles":  len(scored),
            "articles":        scored,
            "fetched_at":      self.last_fetch.isoformat(),
        }

    async def get_cached_or_fresh(self) -> Dict:
        """Return cached if < 5 min old, else fetch fresh"""
        if self.last_fetch and (datetime.now(timezone.utc) - self.last_fetch).seconds < self.fetch_interval:
            bull = sum(a["intensity"] for a in self.cache if a["impact"] == "BULLISH")
            bear = sum(a["intensity"] for a in self.cache if a["impact"] == "BEARISH")
            total = bull + bear or 1
            return {
                "overall_bias":   "BULLISH" if bull/total > 0.6 else "BEARISH" if bear/total > 0.6 else "MIXED",
                "bull_pct":       round(bull/total*100),
                "bear_pct":       round(bear/total*100),
                "high_urgency":   [a for a in self.cache if a.get("urgency") == "HIGH"],
                "articles":       self.cache,
                "fetched_at":     self.last_fetch.isoformat(),
                "from_cache":     True,
            }
        return await self.run()
