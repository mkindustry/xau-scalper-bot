"""
Macro Filter — checks DXY, US10Y, BTC, VIX in real-time
XAU correlations:
  - DXY:  inverse (-0.7 to -0.9)
  - US10Y: inverse (-0.5)
  - BTC:  positive in risk-on regimes (+0.3 to +0.6)
  - VIX:  positive in risk-off (+0.4)
"""
import os
import logging
import aiohttp
import yfinance as yf
from typing import Tuple, List, Dict
from datetime import datetime

log = logging.getLogger("macro")


class MacroFilter:
    def __init__(self):
        self.finnhub_key = os.getenv("FINNHUB_API_KEY", "")

    async def get_context(self) -> Dict:
        """Fetch current macro snapshot via yfinance (free & reliable)"""
        try:
            tickers = {
                "DXY":   "DX-Y.NYB",
                "US10Y": "^TNX",
                "BTC":   "BTC-USD",
                "VIX":   "^VIX",
                "XAU":   "GC=F",
            }
            ctx = {}
            for key, sym in tickers.items():
                t = yf.Ticker(sym)
                hist = t.history(period="2d", interval="1h")
                if len(hist) >= 2:
                    last  = float(hist["Close"].iloc[-1])
                    prev  = float(hist["Close"].iloc[-24] if len(hist) >= 24 else hist["Close"].iloc[0])
                    chg   = ((last - prev) / prev) * 100
                    ctx[key] = {"price": round(last, 2), "chg_24h_pct": round(chg, 2)}
            ctx["timestamp"] = datetime.utcnow().isoformat()
            return ctx
        except Exception as e:
            log.error(f"Macro fetch failed: {e}")
            return {}

    def validate(self, side: str, ctx: Dict) -> Tuple[bool, List[str]]:
        """Return (pass, reasons). Veto if strong opposing macro."""
        reasons = []
        if not ctx:
            return True, ["macro_data_unavailable_allowed"]

        dxy_chg   = ctx.get("DXY",   {}).get("chg_24h_pct", 0)
        yield_chg = ctx.get("US10Y", {}).get("chg_24h_pct", 0)
        btc_chg   = ctx.get("BTC",   {}).get("chg_24h_pct", 0)
        vix       = ctx.get("VIX",   {}).get("price",       20)

        if side == "BUY":
            if dxy_chg > 0.5:
                return False, [f"DXY strongly up (+{dxy_chg}%) — veto BUY"]
            if yield_chg > 3.0:
                return False, [f"US10Y spiking (+{yield_chg}%) — veto BUY"]
            if dxy_chg < -0.2: reasons.append(f"DXY weak ({dxy_chg}%) ✓")
            if btc_chg > 1.0:  reasons.append(f"BTC risk-on (+{btc_chg}%) ✓")
            if vix > 22:       reasons.append(f"VIX elevated ({vix}) → safe-haven ✓")

        elif side == "SELL":
            if dxy_chg < -0.5:
                return False, [f"DXY strongly down ({dxy_chg}%) — veto SELL"]
            if yield_chg < -3.0:
                return False, [f"US10Y dropping ({yield_chg}%) — veto SELL"]
            if dxy_chg > 0.2:  reasons.append(f"DXY strong (+{dxy_chg}%) ✓")
            if yield_chg > 0.5:reasons.append(f"Yields rising (+{yield_chg}%) ✓")
            if vix < 16:       reasons.append(f"VIX low ({vix}) → risk-on ✓")

        return True, reasons or ["macro_neutral"]
