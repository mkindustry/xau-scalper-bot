# 🏆 XAU Scalper Bot

Bot de signaux XAU/USD multi-stratégies avec filtres macro, news temps réel, COT Report, ML scoring et dispatch Telegram.

## 🏗️ Architecture

```
TradingView (Pine Script)
    ↓ Webhook JSON
FastAPI Backend
    ├─ Macro Filter (DXY, US10Y, BTC, VIX)
    ├─ News Filter (Finnhub + FF calendar)
    ├─ COT Analyzer (CFTC)
    ├─ ML Filter (XGBoost)
    └─ Claude Haiku (raisonnement)
    ↓
Telegram Signal
```

## 🚀 Installation

### 1. Backend Python

```bash
cd xau-scalper-bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
```

### 2. Déploiement (Railway/Render recommandé — gratuit)

```bash
# Railway
railway login
railway init
railway up

# Ou Render : push sur GitHub, connecte repo, Render autodetect FastAPI
```

Copie l'URL publique (ex: `https://xau-bot.up.railway.app`).

### 3. TradingView

1. Ouvre `pine/xau_scalper_v1.pine`, colle dans Pine Editor, sauvegarde + ajoute au chart XAUUSD M5 ou M15
2. Remplace `REPLACE_ME` par ton `WEBHOOK_SECRET`
3. Crée une alerte : Condition = "XAU Scalper Bot v1" → "Any alert() function call"
4. Webhook URL : `https://xau-bot.up.railway.app/webhook`
5. Message : `{{plot_0}}` (le JSON est déjà dans l'appel `alert()`)
6. **⚠️ TradingView Pro requis** pour webhooks

### 4. Telegram

1. `@BotFather` → `/newbot` → récupère token
2. Ajoute le bot dans ton channel/group → donne-lui admin
3. Récupère chat ID : envoie un message, va sur `https://api.telegram.org/bot<TOKEN>/getUpdates`

### 5. COT weekly update (cron)

```bash
# Crontab : tous les samedis à 10h UTC
0 10 * * 6 cd /app && python -c "from backend.filters.cot_analyzer import COTAnalyzer; import asyncio; asyncio.run(COTAnalyzer().update_cache())"
```

## 📊 Backtest

```bash
# Télécharge historique XAU M15 en CSV (colonnes: time, open, high, low, close, volume)
# Place dans data/xauusd_m15.csv
python backtest/engine.py
```

## 🧠 Entraîner le modèle ML

À faire après accumulation de ~500 signaux historiques labellisés. Template fourni, à compléter dans `backend/filters/ml_filter.py` avec un script d'entraînement qui :
1. Lit les signaux passés + leurs outcomes
2. Entraîne XGBoost sur features macro+signal
3. Sauve dans `backend/models/xgb_filter.pkl`

En attendant, le filtre retourne 0.60 par défaut (trust le signal Pine).

## 🎯 Features

| # | Feature | Statut |
|---|---------|--------|
| 1 | EMA Stack Scalper | ✅ |
| 2 | Spike Scalper M1 | ✅ |
| 3 | Round Number Reactor | ✅ |
| 4 | London Liquidity Sweep | ✅ |
| 5 | Order Blocks + FVG | ✅ |
| 6 | ICT Kill Zones | ✅ |
| 7 | ATR Volatility Filter | ✅ |
| 8 | Confluence Score 0-100 | ✅ |
| 9 | DXY/US10Y/BTC/VIX filter | ✅ |
| 10 | Finnhub News blackout | ✅ |
| 11 | COT Report analyzer | ✅ |
| 12 | ML XGBoost filter | ✅ (model à entraîner) |
| 13 | Raisonnement via Claude | ✅ |
| 14 | Telegram dispatch | ✅ |
| 15 | Backtest engine | ✅ |

## ⚠️ Disclaimer

Ce bot fournit des signaux d'aide à la décision. Il ne constitue pas un conseil en investissement. Le trading du XAU/USD comporte des risques élevés de perte. Risquer uniquement du capital que tu peux te permettre de perdre.
