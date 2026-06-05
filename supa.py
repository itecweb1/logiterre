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

def record_click(email, org_name="", kind="rsvp"):
    """Enregistre un clic (clic sur le bouton = a cliqué le lien)."""
    try:
        return insert("clicks", {"email": email, "org_name": org_name, "kind": kind})
    except Exception:
        return None

def get_clicks():
    try:
        return select("clicks", "select=*&order=created.desc")
    except Exception:
        return []

# ── Journal d'envoi (persistant, remplace email_log.json sur le cloud) ──
def log_sent(email, org_name="", cc="", status="sent"):
    try:
        return insert("sent_log", {"email": email, "org_name": org_name,
                                    "cc": cc, "status": status})
    except Exception:
        return None

def get_sent():
    try:
        return select("sent_log", "select=*&order=sent_at.desc")
    except Exception:
        return []

def sent_emails_set():
    """Set des emails déjà envoyés (pour dédup)."""
    try:
        rows = select("sent_log", "select=email&status=eq.sent")
        return {r["email"].lower().strip() for r in rows if r.get("email")}
    except Exception:
        return set()

def messages_today(per_msg_default=1):
    """Nombre de messages envoyés aujourd'hui (To + CC) pour le quota Hostinger."""
    import datetime
    today = datetime.date.today().isoformat()
    try:
        rows = select("sent_log", f"select=cc,sent_at&status=eq.sent&sent_at=gte.{today}")
        n = 0
        for r in rows:
            cc = (r.get("cc") or "")
            cc_n = len([x for x in cc.split(",") if x.strip()]) if cc else 0
            n += 1 + cc_n
        return n
    except Exception:
        return 0

# ── Désinscriptions (persistant, RGPD) ────────────────────────
def add_unsub(email, reason="link"):
    try:
        return insert("unsubscribes", {"email": email.lower().strip(), "reason": reason})
    except Exception:
        return None

def is_unsub(email):
    try:
        rows = select("unsubscribes", f"select=email&email=eq.{email.lower().strip()}")
        return len(rows) > 0
    except Exception:
        return False

def get_unsubs():
    try:
        return select("unsubscribes", "select=*&order=added_at.desc")
    except Exception:
        return []

# ── Liste de suppression (bounces / plaintes / blocage manuel) ──
def add_suppression(email, reason="manual", note=""):
    """Ajoute une adresse à ne plus jamais contacter (upsert)."""
    try:
        url, _ = _cfg()
        r = requests.post(f"{url}/rest/v1/suppressions",
                          json={"email": email.lower().strip(), "reason": reason, "note": note},
                          headers=_headers({"Prefer": "resolution=merge-duplicates"}), timeout=12)
        r.raise_for_status()
        return True
    except Exception:
        return None

def get_suppressions():
    try:
        return select("suppressions", "select=*&order=created.desc")
    except Exception:
        return []

def is_suppressed(email):
    try:
        rows = select("suppressions", f"select=email&email=eq.{email.lower().strip()}")
        return len(rows) > 0
    except Exception:
        return False

def remove_suppression(email):
    try:
        url, _ = _cfg()
        r = requests.delete(f"{url}/rest/v1/suppressions?email=eq.{email.lower().strip()}",
                            headers=_headers(), timeout=12)
        r.raise_for_status()
        return True
    except Exception:
        return None

def suppressed_set():
    """Set de toutes les adresses supprimées (bounces+plaintes+manuel) pour dédup rapide."""
    try:
        rows = select("suppressions", "select=email")
        return {r["email"].lower().strip() for r in rows if r.get("email")}
    except Exception:
        return set()

# ── Warmup (montée en charge progressive) ──────────────────────
def get_warmup():
    try:
        rows = select("warmup_state", "select=*&id=eq.1")
        return rows[0] if rows else None
    except Exception:
        return None

def set_warmup(start_date, day0_limit=20, active=True):
    try:
        url, _ = _cfg()
        r = requests.post(f"{url}/rest/v1/warmup_state",
                          json={"id": 1, "start_date": start_date,
                                "day0_limit": int(day0_limit), "active": bool(active)},
                          headers=_headers({"Prefer": "resolution=merge-duplicates"}), timeout=12)
        r.raise_for_status()
        return True
    except Exception:
        return None
