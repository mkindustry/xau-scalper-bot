"""
XAU Scalper Bot — Backend FastAPI (v2 avec sentiment géopolitique)
"""
import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from filters.macro_filter import MacroFilter
from filters.news_filter import NewsFilter
from filters.cot_analyzer import COTAnalyzer
from filters.ml_filter import MLFilter
from reasoning.signal_explainer import SignalExplainer
from dispatch.telegram_bot import TelegramDispatcher
from sentiment.geo_sentiment import GeoSentimentEngine
from sentiment.routes import router as sentiment_router

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("xau-bot")

app = FastAPI(title="XAU Scalper Bot v2")

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sentiment_router)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "REPLACE_ME")

macro     = MacroFilter()
news      = NewsFilter()
cot       = COTAnalyzer()
ml        = MLFilter()
explainer = SignalExplainer()
telegram  = TelegramDispatcher()
sentiment = GeoSentimentEngine()


@app.get("/")
async def health():
    return {"status": "ok", "service": "xau-scalper-v2"}


@app.post("/webhook")
async def webhook(req: Request):
    try:
        data = await req.json()
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

    if data.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(401, "Unauthorized")

    log.info(f"📡 {data.get('side')} {data.get('symbol')} @ {data.get('entry')} | score={data.get('score')}")

    # ─── FILTERS ────────────────────────────────────────────────────────────
    macro_ctx = await macro.get_context()
    macro_pass, macro_reasons = macro.validate(data["side"], macro_ctx)
    if not macro_pass:
        return {"status": "rejected", "reason": "macro", "details": macro_reasons}

    news_pass, news_info = await news.check_blackout()
    if not news_pass:
        return {"status": "rejected", "reason": "news_blackout", "details": news_info}

    cot_ctx = cot.get_latest_bias()
    ml_prob = ml.predict(data, macro_ctx, cot_ctx)
    if ml_prob < 0.55:
        return {"status": "rejected", "reason": "ml_low_prob", "prob": ml_prob}

    # ─── SENTIMENT GÉO ──────────────────────────────────────────────────────
    sent = await sentiment.get_cached_or_fresh()
    sent_bias = sent.get("overall_bias", "MIXED")

    # Veto si sentiment fortement opposé au signal
    if data["side"] == "BUY" and sent_bias == "BEARISH" and sent.get("bear_pct", 0) > 70:
        return {"status": "rejected", "reason": "sentiment_bearish_veto", "bear_pct": sent.get("bear_pct")}
    if data["side"] == "SELL" and sent_bias == "BULLISH" and sent.get("bull_pct", 0) > 70:
        return {"status": "rejected", "reason": "sentiment_bullish_veto", "bull_pct": sent.get("bull_pct")}

    # ─── REASONING ──────────────────────────────────────────────────────────
    reasoning = await explainer.explain(
        signal=data, macro=macro_ctx, news=news_info,
        cot=cot_ctx, ml_prob=ml_prob
    )

    # ─── DISPATCH ───────────────────────────────────────────────────────────
    await telegram.send_signal(
        signal=data, reasoning=reasoning, macro=macro_ctx,
        cot=cot_ctx, ml_prob=ml_prob,
        sentiment=sent
    )

    return {"status": "dispatched", "ml_prob": ml_prob, "sentiment_bias": sent_bias}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
