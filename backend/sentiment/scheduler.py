"""
Sentiment Scheduler — tourne en arrière-plan, envoie alertes autonomes
Si une news HIGH urgency + intensité 3 est détectée, alerte Telegram immédiate
Démarre via asyncio.create_task() dans main.py
"""
import asyncio
import logging
from datetime import datetime, timezone
from sentiment.geo_sentiment import GeoSentimentEngine
from dispatch.telegram_bot_v2 import TelegramDispatcher

log = logging.getLogger("scheduler")

ALERT_INTERVAL_SEC = 300   # Vérifie toutes les 5 min
_already_alerted: set = set()  # Évite les doublons sur même article


async def sentiment_watcher():
    engine    = GeoSentimentEngine()
    dispatcher = TelegramDispatcher()
    log.info("🔍 Sentiment watcher started")

    while True:
        try:
            data = await engine.run()
            for article in data.get("high_urgency", []):
                uid = article.get("url", article.get("title", ""))[:80]
                if uid not in _already_alerted and article.get("intensity", 1) >= 3:
                    await dispatcher.send_sentiment_alert(article)
                    _already_alerted.add(uid)
                    log.info(f"🚨 Urgent alert sent: {article.get('title','')[:60]}")
            # Purge les vieilles alertes (garde les 200 dernières)
            if len(_already_alerted) > 200:
                oldest = list(_already_alerted)[:100]
                for o in oldest:
                    _already_alerted.discard(o)
        except Exception as e:
            log.error(f"Sentiment watcher error: {e}")
        await asyncio.sleep(ALERT_INTERVAL_SEC)
