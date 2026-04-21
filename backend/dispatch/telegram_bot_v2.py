"""
TRADESWITHMK BOT — Telegram Dispatcher v2
Envoie les signaux XAU/USD avec raisonnement complet
"""
import os
import logging
import aiohttp
from typing import Dict

log = logging.getLogger("telegram")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

class TelegramDispatcher:
    def __init__(self):
        self.token   = TELEGRAM_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base    = f"https://api.telegram.org/bot{self.token}"

    async def _send(self, text: str):
        if not self.token or not self.chat_id:
            log.warning("Telegram non configuré — token ou chat_id manquant")
            return
        try:
            async with aiohttp.ClientSession() as s:
                await s.post(
                    f"{self.base}/sendMessage",
                    json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                    timeout=aiohttp.ClientTimeout(total=10)
                )
        except Exception as e:
            log.error(f"Telegram send error: {e}")

    async def send_signal(self, signal: Dict, reasoning: str, macro: Dict, cot: Dict, ml_prob: float, sentiment: Dict):
        side     = signal.get("side", "?")
        symbol   = signal.get("symbol", "XAUUSD")
        setup    = signal.get("setup", "?")
        session  = signal.get("session", "?")
        score    = signal.get("score", 0)
        entry    = signal.get("entry", "?")
        sl       = signal.get("sl", "?")
        tp1      = signal.get("tp1", "?")
        tp2      = signal.get("tp2", "?")
        tp3      = signal.get("tp3", "?")
        atr_val  = signal.get("atr", "?")
        adx_val  = signal.get("adx", "?")
        rsi_val  = signal.get("rsi", "?")
        bias     = sentiment.get("overall_bias", "MIXED")
        bull_pct = sentiment.get("bull_pct", 0)
        bear_pct = sentiment.get("bear_pct", 0)
        cot_bias = cot.get("bias", "N/A")

        side_emoji = "🟢 BUY" if side == "BUY" else "🔴 SELL"
        bias_emoji = "📈" if bias == "BULLISH" else "📉" if bias == "BEARISH" else "➡️"

        msg = f"""<b>⚡ TRADESWITHMK BOT — Signal {symbol}</b>

{side_emoji} <b>{setup}</b> | Session: <b>{session}</b>
Score confluence: <b>{score}/100</b>

<b>📍 Niveaux</b>
• Entry: <code>{entry}</code>
• Stop Loss: <code>{sl}</code>
• TP1: <code>{tp1}</code>
• TP2: <code>{tp2}</code>
• TP3: <code>{tp3}</code>

<b>📊 Indicateurs</b>
• ATR: {atr_val} | ADX: {adx_val} | RSI: {rsi_val}
• ML Prob: {ml_prob:.0%}
• COT: {cot_bias}
• {bias_emoji} Sentiment: {bias} ({bull_pct}% bull / {bear_pct}% bear)

<b>🧠 Analyse</b>
{reasoning}

<i>⚠️ Signal d'aide à la décision — pas un conseil en investissement</i>"""

        await self._send(msg)
        log.info(f"Signal Telegram envoyé: {side} {symbol}")

    async def send_sentiment_alert(self, article: Dict):
        title    = article.get("title", "")[:100]
        impact   = article.get("impact", "NEUTRAL")
        urgency  = article.get("urgency", "MEDIUM")
        source   = article.get("source_name", "")
        reason   = article.get("reason", "")
        intensity = "🔥" * min(article.get("intensity", 1), 3)

        impact_emoji = "📈 BULLISH XAU" if impact == "BULLISH" else "📉 BEARISH XAU" if impact == "BEARISH" else "➡️ NEUTRE"

        msg = f"""<b>⚠️ TRADESWITHMK — Alerte Géopolitique</b>

{intensity} <b>{impact_emoji}</b>

<b>{title}</b>
<i>{source}</i>

{reason}

<i>Urgence: {urgency}</i>"""

        await self._send(msg)
