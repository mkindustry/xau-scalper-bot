# Module Sentiment Géopolitique — XAU/USD

## Fichiers

| Fichier | Rôle |
|---|---|
| `geo_sentiment.py` | Moteur principal : fetch + score via Claude Haiku |
| `routes.py` | Endpoints FastAPI `/sentiment/live` `/summary` `/refresh` |
| `scheduler.py` | Watcher autonome — alertes Telegram si news urgente |

## API Endpoints

```
GET  /sentiment/live     → flux complet articles + scores + biais global
GET  /sentiment/summary  → résumé pour webhook filter (bull%, bear%, urgents)
POST /sentiment/refresh  → force re-fetch (contourne le cache 5min)
```

## Variables env requises

```env
NEWS_API_KEY=xxx        # newsapi.org — plan gratuit: 100 req/jour
FINNHUB_API_KEY=xxx     # finnhub.io — gratuit: 60 req/min
ANTHROPIC_API_KEY=xxx   # Scoring via Claude Haiku
```

## Logique d'impact XAU

| Événement | Impact |
|---|---|
| Guerre, escalade, conflit armé | BULLISH 3 |
| Crise bancaire, défaut souverain | BULLISH 3 |
| Fed dovish / pause / cut surprise | BULLISH 2-3 |
| CPI > attentes | BULLISH 2 |
| Demande CB (Chine, Russie, etc.) | BULLISH 1-2 |
| Hausse taux aggressive / hawkish | BEARISH 2 |
| Ceasefire / accord de paix | BEARISH 2 |
| Risk-on / bull équités | BEARISH 1 |
| Inflation < attentes | BEARISH 2 |

## Intégration dans le signal webhook

Le sentiment est utilisé comme **veto final** :
- Si `side=BUY` et biais bearish > 70% → signal rejeté
- Si `side=SELL` et biais bullish > 70% → signal rejeté
- Sinon → biais affiché dans le message Telegram comme contexte
