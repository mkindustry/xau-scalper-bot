"""
XAU Scalper Bot — Backend FastAPI
Receives TradingView webhook → enriches with macro/news/ML → sends to Telegram
"""
import os
import logging
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

from filters.macro_filter import MacroFilter
from filters.news_filter import NewsFilter
from filters.cot_analyzer import COTAnalyzer
from filters.ml_filter import MLFilter
from reasoning.signal_explainer import SignalExplainer
from dispatch.telegram_bot import TelegramDispatcher

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("xau-bot")

app = FastAPI(title="XAU Scalper Bot")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "REPLACE_ME")

# Initialize modules
macro   = MacroFilter()
news    = NewsFilter()
cot     = COTAnalyzer()
ml      = MLFilter()
explainer = SignalExplainer()
telegram = TelegramDispatcher()


@app.get("/")
async def health():
    return {"status": "ok", "service": "xau-scalper"}


@app.post("/webhook")
async def webhook(req: Request):
    try:
        data = await req.json()
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

    if data.get("secret") != WEBHOOK_SECRET:
        log.warning("Webhook rejected: bad secret")
        raise HTTPException(401, "Unauthorized")

    log.info(f"📡 Signal received: {data.get('side')} {data.get('symbol')} @ {data.get('entry')} | setup={data.get('setup')} | score={data.get('score')}")

    # ─── 1) MACRO FILTER — DXY / US10Y / BTC / VIX ─────────────────────────
    macro_ctx = await macro.get_context()
    macro_pass, macro_reasons = macro.validate(data["side"], macro_ctx)
    if not macro_pass:
        log.info(f"❌ Macro filter rejected: {macro_reasons}")
        return {"status": "rejected", "reason": "macro", "details": macro_reasons}

    # ─── 2) NEWS FILTER — High-impact blackout ─────────────────────────────
    news_pass, news_info = await news.check_blackout()
    if not news_pass:
        log.info(f"❌ News blackout: {news_info}")
        return {"status": "rejected", "reason": "news_blackout", "details": news_info}

    # ─── 3) COT POSITIONING CONTEXT ────────────────────────────────────────
    cot_ctx = cot.get_latest_bias()

    # ─── 4) ML FILTER — XGBoost final scoring ──────────────────────────────
    ml_prob = ml.predict(data, macro_ctx, cot_ctx)
    if ml_prob < 0.55:
        log.info(f"❌ ML filter rejected: prob={ml_prob:.2f}")
        return {"status": "rejected", "reason": "ml_low_prob", "prob": ml_prob}

    # ─── 5) REASONING via Claude Haiku ─────────────────────────────────────
    reasoning = await explainer.explain(
        signal=data,
        macro=macro_ctx,
        news=news_info,
        cot=cot_ctx,
        ml_prob=ml_prob
    )

    # ─── 6) DISPATCH to Telegram ───────────────────────────────────────────
    await telegram.send_signal(
        signal=data,
        reasoning=reasoning,
        macro=macro_ctx,
        cot=cot_ctx,
        ml_prob=ml_prob
    )

    log.info(f"✅ Signal dispatched | ml_prob={ml_prob:.2f}")
    return {
        "status": "dispatched",
        "ml_prob": ml_prob,
        "macro": macro_ctx,
        "cot_bias": cot_ctx.get("bias")
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
