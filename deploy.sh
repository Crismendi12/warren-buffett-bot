#!/bin/bash
# deploy.sh — Sube resultados actualizados a Streamlit Cloud.
#
# Flujo mensual:
#   python3 batch.py   # actualiza results_cache.json (5-20 min)
#   ./deploy.sh        # push a GitHub, Streamlit redeploya en ~60s
#
set -e
cd "$(dirname "$0")"

echo "Preparando archivos de datos..."
git add data/results_cache.json data/watchlist.json data/portfolio.json data/preferences.json

if git diff --cached --quiet; then
    echo "Sin cambios. Corre batch.py primero para actualizar el analisis."
    exit 0
fi

git commit -m "Actualizar analisis $(date '+%Y-%m-%d')"
git push origin main

echo ""
echo "Push exitoso. Streamlit Cloud redeploya en ~60 segundos."
echo "La URL de tu app no cambia."
