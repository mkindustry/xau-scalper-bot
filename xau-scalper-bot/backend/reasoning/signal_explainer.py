"""
Signal Explainer — uses Claude Haiku to generate the trade reasoning
Formats the complete context into a human-readable analysis
"""
import os
import logging
import aiohttp
from typing import Dict

log = logging.getLogger("explainer")


class SignalExplainer:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = "claude-haiku-4-5-20251001"

    async def explain(self, signal: Dict, macro: Dict, news: Dict, cot: Dict, ml_prob: float) -> str:
        """Generate reasoning text (French) for the signal"""
        if not self.api_key:
            return self._fallback(signal, macro, cot, ml_prob)

        prompt = f"""Tu es un trader professionnel XAU/USD. Analyse ce setup et donne un raisonnement concis (max 8 puces) en français.

SIGNAL:
- Side: {signal.get('side')}
- Setup: {signal.get('setup')}
- Session: {signal.get('session')}
- Score confluence: {signal.get('score')}/100
- ATR: {signal.get('atr')}, ADX: {signal.get('adx')}, RSI: {signal.get('rsi')}

MACRO:
- DXY: {macro.get('DXY', {}).get('chg_24h_pct', 'N/A')}%
- US10Y: {macro.get('US10Y', {}).get('chg_24h_pct', 'N/A')}%
- BTC: {macro.get('BTC', {}).get('chg_24h_pct', 'N/A')}%
- VIX: {macro.get('VIX', {}).get('price', 'N/A')}

COT (positionnement institutionnel):
- Bias: {cot.get('bias', 'N/A')}
- Percentile 52w: {cot.get('percentile_52w', 'N/A')}%

ML probabilité gain: {ml_prob:.0%}

Donne un raisonnement en 5-8 puces maximum. Pas d'intro, pas de conclusion, juste les puces avec • en début. Sois précis et factuel."""

        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 500,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=15
                ) as r:
                    data = await r.json()
                    return data["content"][0]["text"]
        except Exception as e:
            log.error(f"Claude API failed: {e}")
            return self._fallback(signal, macro, cot, ml_prob)

    def _fallback(self, signal, macro, cot, ml_prob) -> str:
        lines = [
            f"• Setup {signal.get('setup')} détecté en session {signal.get('session')}",
            f"• Score confluence: {signal.get('score')}/100",
            f"• ADX {signal.get('adx')} (trend strength) | RSI {signal.get('rsi')}",
            f"• DXY {macro.get('DXY', {}).get('chg_24h_pct', 'N/A')}% (corrélation inverse)",
            f"• COT bias: {cot.get('bias', 'N/A')}",
            f"• Probabilité ML: {ml_prob:.0%}",
        ]
        return "\n".join(lines)
