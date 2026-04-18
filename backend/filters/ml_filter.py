"""
ML Filter — XGBoost binary classifier
Takes (signal + macro + cot features) → outputs probability of TP1 hit
Train on backtest data: 6-12 months of labeled signals (did TP1 hit before SL?)
"""
import os
import logging
import pickle
import numpy as np
from typing import Dict

log = logging.getLogger("ml")


class MLFilter:
    def __init__(self, model_path: str = "backend/models/xgb_filter.pkl"):
        self.model_path = model_path
        self.model = None
        if os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    self.model = pickle.load(f)
                log.info(f"ML model loaded from {model_path}")
            except Exception as e:
                log.error(f"ML load failed: {e}")

    def _build_features(self, signal: Dict, macro: Dict, cot: Dict) -> np.ndarray:
        """Flatten signal + context into feature vector"""
        setup_map = {"EMA_STACK": 1, "SPIKE": 2, "ROUND_NUMBER": 3, "LIQ_SWEEP": 4, "SMC_OB_FVG": 5, "UNKNOWN": 0}
        session_map = {"ASIA": 1, "LONDON": 2, "NY": 3, "SILVER_BULLET": 4, "OFF": 0}
        bias_map = {"BULLISH_MOMENTUM": 1, "BEARISH_MOMENTUM": -1, "EXTREME_LONG_RISK": -2, "EXTREME_SHORT_RISK": 2, "NEUTRAL": 0, "UNAVAILABLE": 0, "ERROR": 0}

        features = [
            1 if signal.get("side") == "BUY" else -1,
            setup_map.get(signal.get("setup", "UNKNOWN"), 0),
            session_map.get(signal.get("session", "OFF"), 0),
            float(signal.get("score", 50)),
            float(signal.get("atr", 0)),
            float(signal.get("adx", 0)),
            float(signal.get("rsi", 50)),
            float(macro.get("DXY",   {}).get("chg_24h_pct", 0)),
            float(macro.get("US10Y", {}).get("chg_24h_pct", 0)),
            float(macro.get("BTC",   {}).get("chg_24h_pct", 0)),
            float(macro.get("VIX",   {}).get("price",       20)),
            bias_map.get(cot.get("bias", "NEUTRAL"), 0),
            float(cot.get("percentile_52w", 50)),
        ]
        return np.array(features).reshape(1, -1)

    def predict(self, signal: Dict, macro: Dict, cot: Dict) -> float:
        """Return probability of winning trade. If no model → return 0.6 (trust signal)"""
        if self.model is None:
            log.warning("No ML model — defaulting to 0.60 prob")
            return 0.60

        X = self._build_features(signal, macro, cot)
        try:
            prob = float(self.model.predict_proba(X)[0][1])
            return prob
        except Exception as e:
            log.error(f"ML predict failed: {e}")
            return 0.55
