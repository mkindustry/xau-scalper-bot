"""
Telegram Dispatcher v2 — inclut le bloc sentiment géopolitique dans le signal
"""
import os
import logging
import aiohttp
from typing import Dict

log = logging.getLogger("telegram")

IMPACT_EMOJI = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}
URGENCY_EMOJI = {"HIGH": "🚨", "MEDIUM": "⚡", "LOW": "💬"}
INTENSITY_BAR = {1: "▪", 2: "▪▪", 3: "▪▪▪"}


class TelegramDispatcher:
    def __init__(self):
        self.token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    async def send_signal(
        self,
        signal: Dict,
        reasoning: str,
        macro: Dict,
        cot: Dict,
        ml_prob: float,
        sentiment: Dict = None
    ):
        if not self.token or not self.chat_id:
            log.warning("Telegram credentials missing")
            return

        side  = signal.get("side")
        emoji = "🟢" if side == "BUY" else "🔴"
        entry = signal.get("entry")
        sl    = signal.get("sl")
        tp1   = signal.get("tp1")
        tp2   = signal.get("tp2")
        tp3   = signal.get("tp3")
        r_pts = abs(float(entry) - float(sl))

        # ─── Bloc sentiment ─────────────────────────────────────────────────
        sent_block = ""
        if sentiment:
            bias      = sentiment.get("overall_bias", "MIXED")
            bull_pct  = sentiment.get("bull_pct", 50)
            bear_pct  = sentiment.get("bear_pct", 50)
            urgent    = sentiment.get("high_urgency", [])[:2]

            bar_bull = "█" * (bull_pct // 10) + "░" * (10 - bull_pct // 10)
            bar_bear = "█" * (bear_pct // 10) + "░" * (10 - bear_pct // 10)

            urgent_lines = ""
            for u in urgent:
                urg_emoji = URGENCY_EMOJI.get(u.get("urgency", "LOW"), "💬")
                imp_emoji = IMPACT_EMOJI.get(u.get("impact", "NEUTRAL"), "⚪")
                bar       = INTENSITY_BAR.get(u.get("intensity", 1), "▪")
                title     = u.get("title", "")[:60]
                reason    = u.get("reason", "")
                urgent_lines += f"\n  {urg_emoji}{imp_emoji} {bar} {title}\n      └ {reason}"

            sent_block = f"""
<b>📰 SENTIMENT GÉOPOLITIQUE:</b>
🟢 Bullish  {bar_bull}  {bull_pct}%
🔴 Bearish  {bar_bear}  {bear_pct}%
Biais global: <b>{bias}</b>
{f"<b>🚨 NEWS URGENTES:{urgent_lines}</b>" if urgent else ""}"""

        msg = f"""{emoji} <b>XAU/USD — {side}</b>
━━━━━━━━━━━━━━━━━━━━━━━

📍 <b>Session:</b> {signal.get('session')}
🎯 <b>Setup:</b> {signal.get('setup')}
📊 <b>Score confluence:</b> {signal.get('score')}/100
🤖 <b>ML probabilité:</b> {ml_prob:.0%}

<b>🧠 RAISONNEMENT:</b>
{reasoning}

<b>📈 PLAN DE TRADE:</b>
├ Entry:    <code>{entry}</code>
├ Stop Loss: <code>{sl}</code>  ({r_pts:.2f} pts = 1R)
├ TP1: <code>{tp1}</code>  (+1R — clôturer 50%)
├ TP2: <code>{tp2}</code>  (+2R — clôturer 30%)
└ TP3: <code>{tp3}</code>  (+3R — trail 20%)

<b>⚖️ GESTION:</b>
• Risquer max 0.5% capital | BE à +1R | Trail ATR après TP2
{sent_block}
<b>🌍 MACRO RAPIDE:</b>
• DXY {macro.get('DXY',{}).get('chg_24h_pct','N/A')}% | US10Y {macro.get('US10Y',{}).get('chg_24h_pct','N/A')}% | VIX {macro.get('VIX',{}).get('price','N/A')}
• COT: {cot.get('bias','N/A')} ({cot.get('percentile_52w','N/A')}%ile)

<i>⚠️ Signal d'aide à la décision uniquement.</i>"""

        url     = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}

        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, timeout=10) as r:
                    if r.status != 200:
                        log.error(f"Telegram {r.status}: {await r.text()}")
        except Exception as e:
            log.error(f"Telegram dispatch error: {e}")

    async def send_sentiment_alert(self, article: Dict):
        """Alerte standalone pour news ultra-urgente (même sans signal de trade)"""
        if not self.token or not self.chat_id:
            return

        imp   = article.get("impact", "NEUTRAL")
        emoji = IMPACT_EMOJI.get(imp, "⚪")
        bar   = INTENSITY_BAR.get(article.get("intensity", 1), "▪")

        msg = f"""🚨 <b>NEWS URGENTE XAU/USD</b>

{emoji} Impact: <b>{imp}</b> {bar}
📰 {article.get('title', '')}
💬 {article.get('reason', '')}
🔗 <a href="{article.get('url','')}">Lire</a>
⏰ {article.get('published_at','')[:16]}

<i>Surveiller le price action XAU/USD.</i>"""

        payload = {"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"https://api.telegram.org/bot{self.token}/sendMessage", json=payload, timeout=10) as r:
                    if r.status != 200:
                        log.error(f"Alert send failed: {r.status}")
        except Exception as e:
            log.error(f"Alert error: {e}")
