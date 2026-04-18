"""
Backtest Engine — replay strategy on historical XAU/USD data
Uses vectorbt for speed + comprehensive metrics
Run: python backtest/engine.py
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime


class XAUBacktest:
    def __init__(self, data_path: str, initial_capital: float = 10000):
        self.data_path = data_path
        self.capital = initial_capital
        self.trades = []

    def load_data(self) -> pd.DataFrame:
        """Load XAU M5/M15 OHLCV. Expected cols: time, open, high, low, close, volume"""
        df = pd.read_csv(self.data_path, parse_dates=["time"])
        df = df.sort_values("time").reset_index(drop=True)
        return df

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df["ema8"]  = df["close"].ewm(span=8,   adjust=False).mean()
        df["ema21"] = df["close"].ewm(span=21,  adjust=False).mean()
        df["ema55"] = df["close"].ewm(span=55,  adjust=False).mean()
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

        hl  = df["high"] - df["low"]
        hc  = (df["high"] - df["close"].shift()).abs()
        lc  = (df["low"]  - df["close"].shift()).abs()
        tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14).mean()

        delta = df["close"].diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss
        df["rsi"] = 100 - 100 / (1 + rs)

        df["hour"] = df["time"].dt.hour
        df["in_london"] = (df["hour"] >= 7) & (df["hour"] < 10)
        df["in_ny"]     = (df["hour"] >= 12) & (df["hour"] < 15)
        df["in_kz"]     = df["in_london"] | df["in_ny"]
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        ema_bull = (df["ema8"] > df["ema21"]) & (df["ema21"] > df["ema55"])
        ema_bear = (df["ema8"] < df["ema21"]) & (df["ema21"] < df["ema55"])

        pb_long  = ema_bull & (df["low"].shift(1) <= df["ema21"].shift(1)) & (df["close"] > df["open"])
        pb_short = ema_bear & (df["high"].shift(1) >= df["ema21"].shift(1)) & (df["close"] < df["open"])

        vol_ok = (df["atr"] > 1.5) & (df["atr"] < 15)
        df["long_sig"]  = pb_long  & vol_ok & df["in_kz"]
        df["short_sig"] = pb_short & vol_ok & df["in_kz"]
        return df

    def run(self, sl_atr_mult: float = 1.5, tp_r: float = 2.0) -> dict:
        df = self.load_data()
        df = self.compute_indicators(df)
        df = self.generate_signals(df)

        trades = []
        i = 0
        while i < len(df) - 1:
            row = df.iloc[i]
            if row["long_sig"]:
                entry = row["close"]
                sl    = entry - row["atr"] * sl_atr_mult
                tp    = entry + (entry - sl) * tp_r
                result = self._simulate_trade(df, i, "LONG", entry, sl, tp)
                trades.append(result)
                i = result["exit_idx"] + 1
                continue
            if row["short_sig"]:
                entry = row["close"]
                sl    = entry + row["atr"] * sl_atr_mult
                tp    = entry - (sl - entry) * tp_r
                result = self._simulate_trade(df, i, "SHORT", entry, sl, tp)
                trades.append(result)
                i = result["exit_idx"] + 1
                continue
            i += 1

        return self._compute_metrics(trades)

    def _simulate_trade(self, df, entry_idx, side, entry, sl, tp):
        for j in range(entry_idx + 1, min(entry_idx + 200, len(df))):
            bar = df.iloc[j]
            if side == "LONG":
                if bar["low"] <= sl:
                    return {"side": side, "entry": entry, "exit": sl, "pnl_r": -1, "exit_idx": j}
                if bar["high"] >= tp:
                    return {"side": side, "entry": entry, "exit": tp, "pnl_r": (tp-entry)/(entry-sl), "exit_idx": j}
            else:
                if bar["high"] >= sl:
                    return {"side": side, "entry": entry, "exit": sl, "pnl_r": -1, "exit_idx": j}
                if bar["low"] <= tp:
                    return {"side": side, "entry": entry, "exit": tp, "pnl_r": (entry-tp)/(sl-entry), "exit_idx": j}
        last = df.iloc[min(entry_idx + 200, len(df) - 1)]
        pnl = (last["close"] - entry) / (entry - sl) if side == "LONG" else (entry - last["close"]) / (sl - entry)
        return {"side": side, "entry": entry, "exit": last["close"], "pnl_r": pnl, "exit_idx": entry_idx + 200}

    def _compute_metrics(self, trades):
        if not trades:
            return {"error": "no trades"}
        df = pd.DataFrame(trades)
        wins = df[df["pnl_r"] > 0]
        losses = df[df["pnl_r"] <= 0]
        return {
            "total_trades":   len(df),
            "winrate":        round(len(wins) / len(df) * 100, 2),
            "avg_r":          round(df["pnl_r"].mean(), 2),
            "profit_factor":  round(wins["pnl_r"].sum() / abs(losses["pnl_r"].sum()), 2) if len(losses) else float("inf"),
            "total_r":        round(df["pnl_r"].sum(), 2),
            "max_dd_r":       round(df["pnl_r"].cumsum().cummax().sub(df["pnl_r"].cumsum()).max(), 2),
            "best_trade":     round(df["pnl_r"].max(), 2),
            "worst_trade":    round(df["pnl_r"].min(), 2),
        }


if __name__ == "__main__":
    bt = XAUBacktest("data/xauusd_m15.csv")
    metrics = bt.run()
    print("\n═══ BACKTEST RESULTS ═══")
    for k, v in metrics.items():
        print(f"  {k:20s}: {v}")
