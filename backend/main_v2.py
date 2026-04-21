"""
TRADESWITHMK BOT — Backend FastAPI v2
Signal XAU/USD avec filtres macro, news, COT, ML, sentiment géopolitique
"""
import os
import logging
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

from filters.macro_filter import MacroFilter
from filters.news_filter import NewsFilter
from filters.cot_analyzer import COTAnalyzer
from filters.ml_filter import MLFilter
from reasoning.signal_explainer import SignalExplainer
from dispatch.telegram_bot_v2 import TelegramDispatcher
from sentiment.geo_sentiment import GeoSentimentEngine
from sentiment.routes import router as sentiment_router
from sentiment.scheduler import sentiment_watcher

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("tradeswithmk-bot")

app = FastAPI(title="TRADESWITHMK BOT v2", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(sentiment_router)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "xau2024secretbot")

macro     = MacroFilter()
news      = NewsFilter()
cot       = COTAnalyzer()
ml        = MLFilter()
explainer = SignalExplainer()
telegram  = TelegramDispatcher()
sentiment = GeoSentimentEngine()

_DASH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard.html")

def _load_dashboard():
    try:
        with open(_DASH_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log.warning(f"Dashboard not found: {e}")
        return "<h1>TRADESWITHMK BOT v2 — API Online</h1><p><a href='/docs'>Swagger Docs</a> | <a href='/health'>Health</a></p>"

@app.on_event("startup")
async def startup():
    asyncio.create_task(sentiment_watcher())
    log.info("🚀 TRADESWITHMK BOT v2 démarré")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=_load_dashboard())

@app.get("/health")
async def health():
    return {"status": "ok", "service": "tradeswithmk-bot", "version": "2.0.0"}

@app.post("/webhook")
async def webhook(req: Request):
    try:
        data = await req.json()
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

    if data.get("secret") != WEBHOOK_SECRET:
        log.warning("Webhook: secret invalide")
        raise HTTPException(401, "Unauthorized")

    log.info(f"📶 Signal reçu: {data.get('side')} {data.get('symbol')} @ {data.get('entry')} | score={data.get('score')}")

    # Filtre 1 — Macro
    macro_ctx = await macro.get_context()
    macro_pass, macro_reasons = macro.validate(data["side"], macro_ctx)
    if not macro_pass:
        log.info(f"❌ Rejeté macro: {macro_reasons}")
        return {"status": "rejected", "reason": "macro", "details": macro_reasons}

    # Filtre 2 — News blackout
    news_pass, news_info = await news.check_blackout()
    if not news_pass:
        log.info(f"❌ Rejeté news blackout: {news_info}")
        return {"status": "rejected", "reason": "news_blackout", "details": news_info}

    # Filtre 3 — COT + ML
    cot_ctx = cot.get_latest_bias()
    ml_prob = ml.predict(data, macro_ctx, cot_ctx)
    if ml_prob < 0.55:
        log.info(f"❌ Rejeté ML: prob={ml_prob:.2f}")
        return {"status": "rejected", "reason": "ml_low_prob", "prob": ml_prob}

    # Filtre 4 — Sentiment géopolitique
    sent = await sentiment.get_cached_or_fresh()
    sent_bias = sent.get("overall_bias", "MIXED")
    if data["side"] == "BUY" and sent_bias == "BEARISH" and sent.get("bear_pct", 0) > 70:
        return {"status": "rejected", "reason": "sentiment_bearish_veto"}
    if data["side"] == "SELL" and sent_bias == "BULLISH" and sent.get("bull_pct", 0) > 70:
        return {"status": "rejected", "reason": "sentiment_bullish_veto"}

    # ✅ Signal validé — raisonnement + dispatch Telegram
    reasoning = await explainer.explain(
        signal=data, macro=macro_ctx, news=news_info,
        cot=cot_ctx, ml_prob=ml_prob
    )
    await telegram.send_signal(
        signal=data, reasoning=reasoning, macro=macro_ctx,
        cot=cot_ctx, ml_prob=ml_prob, sentiment=sent
    )

    log.info(f"✅ Signal dispatché: {data.get('side')} ML={ml_prob:.2f} Sentiment={sent_bias}")
    return {
        "status": "dispatched",
        "ml_prob": round(ml_prob, 3),
        "sentiment_bias": sent_bias,
        "filters_passed": ["macro", "news", "ml", "sentiment"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
