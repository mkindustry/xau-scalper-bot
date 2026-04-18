"""
COT Analyzer — CFTC Commitment of Traders for Gold
Source: https://www.cftc.gov/dea/futures/deacmxsf.htm
Updated every Friday at 15:30 ET (data for prior Tuesday)

Signal: Net positioning of Managed Money / Non-Commercial
  - Extreme long → potential exhaustion (contrarian short bias)
  - Extreme short → potential squeeze (contrarian long bias)
  - Momentum with positioning → confluence
"""
import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict
import aiohttp

log = logging.getLogger("cot")


class COTAnalyzer:
    """
    Simplified COT analyzer using cot_reports python package or CFTC direct fetch.
    For production: cache weekly data in CSV.
    """
    def __init__(self, cache_path: str = "data/cot_history.csv"):
        self.cache_path = cache_path
        self.latest = None

    def get_latest_bias(self) -> Dict:
        """Return latest COT snapshot for Gold"""
        try:
            if os.path.exists(self.cache_path):
                df = pd.read_csv(self.cache_path)
                df = df.sort_values("date").tail(52)  # last year

                last = df.iloc[-1]
                net_nc = last["noncomm_long"] - last["noncomm_short"]

                # Percentile vs 52-week history
                nc_history = df["noncomm_long"] - df["noncomm_short"]
                percentile = (nc_history < net_nc).sum() / len(nc_history) * 100

                # Week-over-week change
                prev = df.iloc[-2]
                wow_change = net_nc - (prev["noncomm_long"] - prev["noncomm_short"])

                bias = "NEUTRAL"
                if percentile > 80:
                    bias = "EXTREME_LONG_RISK"
                elif percentile < 20:
                    bias = "EXTREME_SHORT_RISK"
                elif percentile > 60 and wow_change > 0:
                    bias = "BULLISH_MOMENTUM"
                elif percentile < 40 and wow_change < 0:
                    bias = "BEARISH_MOMENTUM"

                return {
                    "bias": bias,
                    "net_non_commercial": int(net_nc),
                    "percentile_52w": round(percentile, 1),
                    "wow_change": int(wow_change),
                    "date": last["date"]
                }
            else:
                log.warning(f"COT cache not found at {self.cache_path}")
                return {"bias": "UNAVAILABLE"}
        except Exception as e:
            log.error(f"COT analysis failed: {e}")
            return {"bias": "ERROR", "error": str(e)}

    async def update_cache(self):
        """
        Weekly job — pulls latest COT data.
        Recommend running as a cron/scheduler every Saturday.
        Use `cot_reports` package: pip install cot-reports
        """
        try:
            import cot_reports as cot
            df = cot.cot_year(year=datetime.now().year, cot_report_type="legacy_fut")
            gold = df[df["Market_and_Exchange_Names"].str.contains("GOLD", case=False, na=False)]

            out = pd.DataFrame({
                "date":            gold["Report_Date_as_YYYY-MM-DD"],
                "noncomm_long":    gold["Noncommercial_Positions_Long_All"],
                "noncomm_short":   gold["Noncommercial_Positions_Short_All"],
                "comm_long":       gold["Commercial_Positions_Long_All"],
                "comm_short":      gold["Commercial_Positions_Short_All"],
            })
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            out.to_csv(self.cache_path, index=False)
            log.info(f"COT cache updated: {len(out)} rows")
        except Exception as e:
            log.error(f"COT update failed: {e}")
