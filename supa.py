"""LOGITERRE 2026 — Connecteur Supabase (base persistante pour le cloud).
Si SUPABASE_URL + SUPABASE_KEY sont définis (Secrets/env) → utilise Supabase.
Sinon → désactivé (l'app retombe sur SQLite local).
API REST PostgREST via requests (léger, pas de dépendance lourde).
"""
import os
try:
    import requests
except Exception:
    requests = None

def _cfg():
    return (os.environ.get("SUPABASE_URL", "").rstrip("/"),
            os.environ.get("SUPABASE_KEY", ""))

def enabled():
    url, key = _cfg()
    return bool(url and key and requests)

def _headers(extra=None):
    _, key = _cfg()
    h = {"apikey": key, "Authorization": f"Bearer {key}",
         "Content-Type": "application/json"}
    if extra: h.update(extra)
    return h

def insert(table, row):
    url, _ = _cfg()
    r = requests.post(f"{url}/rest/v1/{table}", json=row,
                      headers=_headers({"Prefer": "return=representation"}), timeout=12)
    r.raise_for_status()
    return r.json()

def select(table, query="select=*&order=created.desc"):
    url, _ = _cfg()
    r = requests.get(f"{url}/rest/v1/{table}?{query}", headers=_headers(), timeout=12)
    r.raise_for_status()
    return r.json()

def update(table, match, row):
    url, _ = _cfg()
    r = requests.patch(f"{url}/rest/v1/{table}?{match}", json=row,
                       headers=_headers({"Prefer": "return=representation"}), timeout=12)
    r.raise_for_status()
    return r.json()

def ping():
    """Teste la connexion. Retourne (ok, message)."""
    if not enabled():
        return False, "Supabase non configuré (SUPABASE_URL / SUPABASE_KEY manquants)"
    try:
        select("rsvp", "select=id&limit=1")
        return True, "Connexion Supabase OK ✅"
    except Exception as e:
        return False, f"Erreur : {str(e)[:150]}"

# ── Opérations métier ─────────────────────────────────────────
def save_rsvp(org_name, email, response, delegates=1, speaker=0, notes=""):
    return insert("rsvp", {"org_name": org_name, "email": email, "response": response,
                           "delegates": int(delegates), "speaker": int(speaker), "notes": notes})

def get_rsvps():
    try:
        return select("rsvp", "select=*&order=created.desc")
    except Exception:
        return []

def record_open(email, org_name=""):
    """Enregistre une ouverture (un clic = preuve d'ouverture)."""
    try:
        return insert("opens", {"email": email, "org_name": org_name})
    except Exception:
        return None

def get_opens():
    try:
        return select("opens", "select=*&order=created.desc")
    except Exception:
        return []
