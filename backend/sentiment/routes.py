"""
Sentiment API Routes — FastAPI router
GET  /sentiment/live     → current news + scores + aggregate bias
GET  /sentiment/summary  → aggregated bias for webhook filter
POST /sentiment/refresh  → force re-fetch
"""
import logging
from fastapi import APIRouter, HTTPException
from sentiment.geo_sentiment import GeoSentimentEngine

log = logging.getLogger("sentiment.api")

router   = APIRouter(prefix="/sentiment", tags=["sentiment"])
_engine  = GeoSentimentEngine()


@router.get("/live")
async def get_live_sentiment():
    """Full news feed with scores — used by dashboard"""
    try:
        data = await _engine.get_cached_or_fresh()
        return data
    except Exception as e:
        log.error(f"Sentiment live error: {e}")
        raise HTTPException(500, str(e))


@router.get("/summary")
async def get_summary():
    """Quick sentiment summary for webhook signal filter"""
    data = await _engine.get_cached_or_fresh()
    return {
        "overall_bias": data["overall_bias"],
        "bull_pct":     data["bull_pct"],
        "bear_pct":     data["bear_pct"],
        "high_urgency_count": len(data.get("high_urgency", [])),
        "top_urgent":   data.get("high_urgency", [])[:3],
        "fetched_at":   data["fetched_at"],
    }


@router.post("/refresh")
async def force_refresh():
    """Force full re-fetch (bypass cache)"""
    _engine.last_fetch = None
    data = await _engine.run()
    return {"status": "refreshed", "articles": len(data["articles"])}
