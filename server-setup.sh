#!/bin/bash
# ============================================================
# Script de configuration initiale du serveur (à exécuter UNE FOIS)
# Usage : bash server-setup.sh
# ============================================================
set -e

REPO_URL="https://github.com/asrDIL/assistant.git"
APP_DIR="/opt/assistant"
GEMINI_API_KEY=""  # ← À renseigner avant de lancer ou sera demandé interactivement
GITHUB_TOKEN=""    # ← Optionnel : token GitHub si le dépôt est privé (Settings → Developer settings → PAT)

echo "========================================"
echo " Setup serveur — Assistant Démarches Bénin"
echo "========================================"

# ── 1. Mise à jour système ────────────────────────────────
echo ""
echo "==> [1/6] Mise à jour des paquets..."
apt-get update -y && apt-get upgrade -y

# ── 2. Docker ────────────────────────────────────────────
echo ""
echo "==> [2/6] Installation de Docker..."
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Ajoute l'utilisateur courant au groupe docker (évite sudo)
usermod -aG docker "$USER" || true
echo "Docker installé : $(docker --version)"

# ── 3. Git ────────────────────────────────────────────────
echo ""
echo "==> [3/6] Installation de Git..."
apt-get install -y git

# ── 4. Clonage du dépôt ──────────────────────────────────
echo ""
echo "==> [4/6] Clonage du dépôt dans $APP_DIR..."
mkdir -p /opt

# Construit l'URL avec token si dépôt privé
if [ -n "$GITHUB_TOKEN" ]; then
    CLONE_URL="https://${GITHUB_TOKEN}@github.com/asrDIL/assistant.git"
else
    CLONE_URL="$REPO_URL"
fi

if [ -d "$APP_DIR/.git" ]; then
    echo "   Dossier existant, mise à jour..."
    git -C "$APP_DIR" pull origin main
else
    git clone "$CLONE_URL" "$APP_DIR"
fi
# Stocke les credentials git pour les prochains pulls automatiques
if [ -n "$GITHUB_TOKEN" ]; then
    git -C "$APP_DIR" remote set-url origin "$CLONE_URL"
fi
cd "$APP_DIR"

# ── 5. Fichier .env ──────────────────────────────────────
echo ""
echo "==> [5/6] Création du fichier backend/.env..."
if [ -f "$APP_DIR/backend/.env" ]; then
    echo "   .env déjà présent, on garde l'existant."
else
    if [ -z "$GEMINI_API_KEY" ]; then
        echo ""
        echo "⚠️  GEMINI_API_KEY non défini dans ce script."
        read -r -p "   Entrez votre clé API Gemini : " GEMINI_API_KEY
    fi
    cat > "$APP_DIR/backend/.env" << EOF
GEMINI_API_KEY=$GEMINI_API_KEY
EOF
    echo "   .env créé."
fi

# ── 6. Premier lancement ─────────────────────────────────
echo ""
echo "==> [6/6] Premier lancement avec Docker Compose..."
cd "$APP_DIR"
docker compose up --build -d

echo ""
echo "========================================"
echo " ✅ Setup terminé !"
echo ""
echo " Backend  → http://$(hostname -I | awk '{print $1}'):8000"
echo " Frontend → http://$(hostname -I | awk '{print $1}'):3000"
echo ""
echo " Prochains déploiements : automatiques via GitHub Actions."
echo "========================================"
