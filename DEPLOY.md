# 🚀 Déployer LOGITERRE sur Streamlit Community Cloud

## ✅ Ce qui a été préparé
- `requirements.txt` — dépendances Python
- `packages.txt` — LibreOffice (pour générer les PDF sur le cloud)
- `pdf_gen.py` — génération PDF autonome (plus besoin du plugin local)
- `.gitignore` — protège ta DB, tes logs et tes mots de passe
- Mots de passe lus depuis les **Secrets** (plus en clair dans le code)
- **Protection par mot de passe** (variable `APP_PASSWORD`)

---

## 📋 Étapes

### 1. Compte GitHub + Git
- Crée un compte sur **github.com**
- Sur github.com → **New repository** → nom `logiterre` → **Private** (recommandé) → Create

### 2. Pousser le code (Terminal)
```bash
cd /Users/ayb/Desktop/logiterre-expo
git init
git add interface.py db.py pdf_gen.py email_validator.py dns_checker.py \
        reply_triage.py report_gen.py send_emails.py tracking_server.py \
        academies_clean.py requirements.txt packages.txt .gitignore \
        DOCX_TEMP_ACAD/LOGITERRE_2026_Invitation_ALICE.docx
git commit -m "LOGITERRE 2026 platform"
git remote add origin https://github.com/TON-USER/logiterre.git
git branch -M main
git push -u origin main
```
> ⚠️ Le `.gitignore` empêche d'envoyer `email_log.json`, `logiterre.db` et `secrets.toml`.
> Le template DOCX est ajouté explicitement (nécessaire aux PDF).

### 3. Déployer
- Va sur **share.streamlit.io** → "Continue with GitHub"
- **New app** → ton dépôt `logiterre` → branche `main` → fichier `interface.py`
- **Deploy**

### 4. Secrets (Settings → Secrets)
Colle ceci (avec tes vraies valeurs) :
```toml
SMTP_USER     = "a.zahraoui@logiterre-expo.com"
SMTP_PASSWORD = "ton-mot-de-passe-email"
IMAP_USER     = "a.zahraoui@logiterre-expo.com"
IMAP_PASSWORD = "ton-mot-de-passe-email"
APP_PASSWORD  = "un-mot-de-passe-pour-proteger-l-app"
```
→ `APP_PASSWORD` protège l'accès. Sans lui, l'app serait ouverte à tous.

### 5. C'est en ligne 🌍
URL : `https://ton-app.streamlit.app`

---

## ⚠️ Limites de Streamlit Cloud (à connaître)

| Limite | Impact | Solution |
|---|---|---|
| **Données éphémères** | DB + log s'effacent au redéploiement | Exporter régulièrement (Paramètres → Export) |
| **Pas de 2ᵉ serveur** | Tracking pixel/RSVP ne tourne pas | Lancer `tracking_server.py` + cloudflared sur ton Mac, coller l'URL dans Composer |
| **L'app dort** | Envoi long coupé si onglet fermé | Garder l'onglet ouvert, ou faire des lots courts |
| **Public (même avec mdp)** | App accessible via URL | `APP_PASSWORD` obligatoire |

---

## 🏆 Alternative pour une vraie production
Un **VPS Hostinger (~5€/mois)** : toujours en ligne, privé, données conservées,
tracking + envoi qui tournent en continu. Idéal si la campagne dure plusieurs jours.
