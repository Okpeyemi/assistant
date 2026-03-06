# Guide de déploiement — Assistant Démarches Bénin

## Architecture

```
GitHub (push) → GitHub Actions → SSH → Serveur Ubuntu
                                         ├── Docker (backend :8000)
                                         └── Docker (frontend :3000)
```

---

## Étape 1 — Préparer le serveur (une seule fois)

### 1.1 Se connecter au serveur

```bash
ssh root@<IP_SERVEUR>
```

### 1.2 Lancer le script de setup automatique

```bash
curl -fsSL https://raw.githubusercontent.com/asrDIL/assistant/main/server-setup.sh | bash
```

> Ce script installe Docker, clone le repo, crée le `.env` et lance les conteneurs.

### 1.3 Vérifier que tout tourne

```bash
docker compose -f /opt/assistant/docker-compose.yml ps
```

L'application est accessible via :
- **Frontend** → `http://<IP_SERVEUR>:3000`
- **Backend API** → `http://<IP_SERVEUR>:8000`

---

## Étape 2 — Configurer GitHub Actions (une seule fois)

Va dans ton dépôt GitHub → **Settings → Secrets and variables → Actions** → **New repository secret**

Crée ces 4 secrets :

| Nom du secret     | Valeur                          |
|-------------------|---------------------------------|
| `SERVER_HOST`     | IP de ton serveur (ex: `154.x.x.x`) |
| `SERVER_USER`     | `root` (ou ton user SSH)        |
| `SERVER_PASSWORD` | Ton mot de passe SSH            |
| `SERVER_PORT`     | `22`                            |

---

## Étape 3 — Déploiement automatique

À chaque `git push` sur la branche `main` :

1. GitHub Actions lance le job `deploy`
2. Il se connecte en SSH à ton serveur
3. Execute `git pull` + `docker compose up --build -d`
4. Les conteneurs sont redémarrés avec le nouveau code

Tu peux voir les logs dans l'onglet **Actions** de ton dépôt GitHub.

---

## Mises à jour manuelles (si besoin)

```bash
ssh root@<IP_SERVEUR>
cd /opt/assistant
git pull origin main
docker compose up --build -d
```

---

## Gestion des conteneurs

```bash
# Voir l'état
docker compose -f /opt/assistant/docker-compose.yml ps

# Voir les logs
docker compose -f /opt/assistant/docker-compose.yml logs -f

# Redémarrer
docker compose -f /opt/assistant/docker-compose.yml restart

# Arrêter
docker compose -f /opt/assistant/docker-compose.yml down
```

---

## Modifier la clé Gemini sur le serveur

```bash
nano /opt/assistant/backend/.env
# Modifier GEMINI_API_KEY=...
docker compose -f /opt/assistant/docker-compose.yml restart backend
```
