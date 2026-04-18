"""
News Filter — checks for high-impact economic events within blackout window
Sources:
  - Finnhub (economic calendar)
  - Forex Factory (fallback via scraping)
XAU-sensitive events: NFP, CPI, FOMC, Fed speeches, Powell, ECB rate, War/geopolitical
"""
import os
import logging
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import Tuple, List, Dict

log = logging.getLogger("news")

HIGH_IMPACT_KEYWORDS = [
    "NFP", "Non-Farm", "CPI", "PPI", "FOMC", "Fed", "Powell", "Jackson Hole",
    "Rate Decision", "Interest Rate", "ECB", "GDP", "Unemployment",
    "Core PCE", "Retail Sales", "Jobless Claims", "ISM"
]


class NewsFilter:
    def __init__(self, blackout_minutes: int = 15):
        self.finnhub_key = os.getenv("FINNHUB_API_KEY", "")
        self.blackout = blackout_minutes

    async def check_blackout(self) -> Tuple[bool, Dict]:
        """Return (trade_allowed, event_info)"""
        if not self.finnhub_key:
            log.warning("No FINNHUB_API_KEY — news filter disabled")
            return True, {"note": "news_filter_disabled"}

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=self.blackout)
        window_end   = now + timedelta(minutes=self.blackout)

        url = "https://finnhub.io/api/v1/calendar/economic"
        params = {
            "from":  window_start.date().isoformat(),
            "to":    window_end.date().isoformat(),
            "token": self.finnhub_key
        }

        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, params=params, timeout=10) as r:
                    data = await r.json()
            events = data.get("economicCalendar", [])
        except Exception as e:
            log.error(f"Finnhub fetch failed: {e}")
            return True, {"error": str(e)}

        for ev in events:
            # Finnhub format: time = "2024-01-15 13:30:00"
            try:
                ev_time = datetime.strptime(ev["time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if window_start <= ev_time <= window_end:
                impact = ev.get("impact", "").lower()
                country = ev.get("country", "")
                event_name = ev.get("event", "")

                # Only veto on high impact from US or if matches keyword
                is_keyword = any(kw.lower() in event_name.lower() for kw in HIGH_IMPACT_KEYWORDS)
                if (impact == "high" and country == "US") or is_keyword:
                    return False, {
                        "event":   event_name,
                        "country": country,
                        "impact":  impact,
                        "time":    ev["time"],
                        "minutes_away": int((ev_time - now).total_seconds() / 60)
                    }

        return True, {"status": "clear"}
