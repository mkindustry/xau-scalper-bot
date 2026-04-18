#!/bin/bash
# ═══════════════════════════════════════════════════════
# XAU Scalper Bot — Push automatique vers GitHub
# Usage: bash push_to_github.sh
# ═══════════════════════════════════════════════════════

REPO_URL="https://github.com/mkindustry/xau-scalper-bot.git"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   XAU Scalper Bot — Push vers GitHub     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Vérifier si git est installé
if ! command -v git &> /dev/null; then
    echo "❌ Git n'est pas installé. Installe-le d'abord :"
    echo "   https://git-scm.com/downloads"
    exit 1
fi

# Initialiser git si pas déjà fait
if [ ! -d ".git" ]; then
    echo "📁 Initialisation du repo git..."
    git init
    git branch -M main
fi

# Configurer le remote
if git remote get-url origin &>/dev/null; then
    echo "🔗 Remote origin déjà configuré, mise à jour..."
    git remote set-url origin "$REPO_URL"
else
    echo "🔗 Ajout du remote origin..."
    git remote add origin "$REPO_URL"
fi

# Ajouter tous les fichiers
echo "📦 Ajout des fichiers..."
git add .

# Commit
echo "💾 Commit..."
git commit -m "🚀 XAU Scalper Bot v1 — Multi-strategy + Sentiment + ML" 2>/dev/null || \
git commit -m "Update: $(date '+%Y-%m-%d %H:%M')"

# Push
echo "🚀 Push vers GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Projet pushé avec succès !"
    echo "   👉 https://github.com/mkindustry/xau-scalper-bot"
    echo ""
    echo "Prochaine étape : Railway"
    echo "   👉 https://railway.app → New Project → Deploy from GitHub"
    echo ""
else
    echo ""
    echo "❌ Push échoué. Vérifie :"
    echo "   1. Tu es connecté à GitHub (gh auth login)"
    echo "   2. Le repo existe sur GitHub"
    echo "   3. Tu as les droits en écriture"
    echo ""
    echo "Alternative — push avec token personnel :"
    echo "   git remote set-url origin https://TON_TOKEN@github.com/mkindustry/xau-scalper-bot.git"
    echo "   git push -u origin main"
fi
