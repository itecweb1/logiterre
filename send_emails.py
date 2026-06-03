#!/usr/bin/env python3
"""
LOGITERRE 2026 — Envoi optimisé Hostinger anti-spam.

Configuration anti-blocage :
  - 90 à 180 secondes entre emails (aléatoire — comportement humain)
  - Reconnexion SMTP entre chaque envoi (pas une longue session)
  - En-têtes professionnels (Reply-To, Message-ID, Date, X-Mailer)
  - Lots de 25 emails par jour maximum (sous le radar Hostinger)
  - Retry automatique en cas d'erreur transitoire
  - Reprise après interruption (--resume)

Usage:
    python3 send_emails.py --test                     # Test (1 email à vous-même)
    python3 send_emails.py --batch 25 --yes           # 25 emails (≈ 60-90 min)
    python3 send_emails.py --range 26 50 --yes        # Reprendre demain
    python3 send_emails.py --range 51 71 --yes        # Finir après-demain
    python3 send_emails.py --resume --yes             # Continuer ceux non envoyés

Conseils :
    - Lancez 25 emails maximum par JOUR
    - Étalez les 71 institutions sur 3 jours
    - Vérifiez votre boîte d'envoi entre chaque batch
"""

import argparse
import random
import smtplib
import ssl
import sys
import time
import json
import uuid
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, '/tmp')
# Use cleaned list (only validated emails) if it exists
try:
    from academies_clean import ACADEMIES
    print("✓ Using academies_clean.py (validated emails only)")
except ImportError:
    from academies import ACADEMIES
    print("⚠ Using academies.py (NOT validated)")

# ============================================================
# CONFIGURATION HOSTINGER (SMTP)
# ============================================================
import os as _os
from pathlib import Path as _Path

def _secret(key, default=""):
    """Lit un secret : variable d'environnement (cloud) puis .streamlit/secrets.toml (local).
    Aucun mot de passe n'est écrit en dur — le fichier secrets.toml est gitignoré."""
    v = _os.environ.get(key)
    if v:
        return v
    try:
        import tomllib
        p = _Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
        if p.exists():
            with open(p, "rb") as f:
                data = tomllib.load(f)
            if key in data:
                return str(data[key])
    except Exception:
        pass
    return default

SMTP_SERVER   = "smtp.hostinger.com"
SMTP_PORT     = 465                                    # SSL
SMTP_USER     = _secret("SMTP_USER", "a.zahraoui@logiterre-expo.com")
SMTP_PASSWORD = _secret("SMTP_PASSWORD")               # vide si non configuré (jamais en dur)

FROM_NAME  = "LOGITERRE 2026 - Office of the Secretary General"
FROM_EMAIL = SMTP_USER
REPLY_TO   = "sg@logiterre-expo.com"

# CC fixes
CC_EMAILS = [
    "contact@uaotlafrica.com",
    "sg@logiterre-expo.com",
]

# Test
TEST_EMAIL = "a.zahraoui@logiterre-expo.com"

# Anti-spam : delays aléatoires entre 90 et 180 secondes (1m30 à 3m)
MIN_DELAY = 90
MAX_DELAY = 180

# Délai après échec puis retry
RETRY_DELAY = 60
MAX_RETRIES = 2

# ============================================================
# CONTENU
# ============================================================
PDF_DIR  = Path("/Users/ayb/Desktop/logiterre-expo/PDF_ACADEMIES")
LOG_FILE = Path("/Users/ayb/Desktop/logiterre-expo/email_log.json")

SUBJECT = "Official Invitation – LOGITERRE 2026 Plenary Session & International Transport and Logistics Forum & Exhibition."

BODY = """Dear Sir / Madam,

I hope this message finds you well.

On behalf of the LOGITERRE 2026 Organizing Committee, it is my great honor to share with you the attached official invitation letter regarding the Third Edition of the International LOGITERRE Forum & Exhibition, scheduled to take place in Casablanca, Kingdom of Morocco, from 20 to 22 October 2026.

Organized under the High Patronage of His Majesty King Mohammed VI, LOGITERRE 2026 will convene high-level institutional leaders, policymakers, international organizations, academia, research centers, infrastructure experts, and major industry stakeholders to discuss the future of transport, logistics, smart mobility, sustainable infrastructure, and strategic connectivity ecosystems across Africa and the global economy.

Considering the recognized expertise and international standing of your esteemed institution, we would be profoundly honored to welcome your participation and valuable contribution to this major international gathering.

Please find attached for your kind consideration:
  - Official Invitation Letter
  - LOGITERRE 2026 Presentation Brochure
  - Concept Note
  - https://linktr.ee/LOGITERRE.PRO

We remain entirely at your disposal for any further information, coordination, or discussions regarding participation modalities, speaking opportunities, institutional partnerships, or cooperation frameworks.

We sincerely look forward to the privilege of welcoming your esteemed institution to Casablanca - LOGITERRE 2026.

With highest consideration and respect,

Office of the Secretary General
LOGITERRE 2026 Organizing Committee
Email: sg@logiterre-expo.com
Tel / WhatsApp / WeChat / Telegram: +212 673 642 4246
"""

# ============================================================
# HELPERS
# ============================================================
def safe_filename(name: str) -> str:
    import re
    return re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_')


def load_log():
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_log(log):
    LOG_FILE.write_text(json.dumps(log, indent=2, ensure_ascii=False))


def build_message(org, recipient_emails, test_mode=False):
    msg = EmailMessage()

    # En-têtes anti-spam : format professionnel
    msg["From"]         = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"]           = ", ".join(recipient_emails)
    msg["Cc"]           = ", ".join(CC_EMAILS)
    msg["Reply-To"]     = REPLY_TO
    msg["Date"]         = formatdate(localtime=True)
    msg["Message-ID"]   = make_msgid(domain="logiterre-expo.com")
    msg["X-Mailer"]     = "LOGITERRE 2026 Secretariat"
    msg["X-Priority"]   = "3"  # Normal

    # Subject / body : override par-destinataire (auto-template) si fourni
    subject = org.get("subject_override") or SUBJECT
    if test_mode:
        subject = "[TEST] " + subject
    msg["Subject"] = subject

    body_text = org.get("body_override") or BODY
    track_id  = org.get("track_id")
    track_url = globals().get("TRACK_BASE_URL", "")
    app_url   = _os.environ.get("APP_URL", "").rstrip("/")   # URL de l'app cloud (RSVP)
    org_name  = org.get("name", "")
    to_email  = (recipient_emails[0] if recipient_emails else "")

    # Lien RSVP : priorité à l'app cloud (marche sans Mac), sinon serveur tracking
    import urllib.parse as _up
    rsvp_link = None
    if app_url and track_id:
        q = _up.urlencode({"rsvp": track_id, "org": org_name, "email": to_email})
        rsvp_link = f"{app_url}/?{q}"
    elif track_url and track_id:
        rsvp_link = f"{track_url}/register/{track_id}"
    unsub_link = f"{track_url}/u/{track_id}" if (track_url and track_id) else None

    # Texte brut
    if rsvp_link:
        body_text += f"\n\n👉 Confirm your participation : {rsvp_link}"
    if unsub_link:
        body_text += f"\n\n---\nUnsubscribe : {unsub_link}"

    msg.set_content(body_text)

    # Version HTML : bouton RSVP + (pixel si serveur tracking) + désinscription
    if rsvp_link or (track_url and track_id):
        html_body = body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_body = html_body.split("👉 Confirm")[0]
        html_body = html_body.replace("\n", "<br>\n")
        cta = ""
        if rsvp_link:
            cta = (f'<div style="text-align:center;margin:24px 0;">'
                   f'<a href="{rsvp_link}" '
                   f'style="background:#302b63;color:#fff;text-decoration:none;padding:14px 32px;'
                   f'border-radius:10px;font-weight:bold;font-size:15px;display:inline-block;">'
                   f'✅ Confirm your participation</a></div>')
        pixel = (f'<img src="{track_url}/pixel/{track_id}.png" width="1" height="1" '
                 f'style="display:none" alt="">') if (track_url and track_id) else ""
        unsub = (f'<br><br><span style="font-size:11px;color:#999;">'
                 f'Pour vous désinscrire : <a href="{unsub_link}">cliquez ici</a></span>') if unsub_link else ""
        # Logo LogiTerre en en-tête (image inline CID — fiable dans la plupart des clients)
        logo_path = _Path(__file__).resolve().parent / "logo.png"
        logo_header = ""
        if logo_path.exists():
            logo_header = ('<div style="text-align:center;margin-bottom:18px;">'
                           '<img src="cid:logiterrelogo" style="max-width:300px;width:60%;"></div>')
        html = (f'<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#222;">'
                f'{logo_header}{html_body}{cta}{unsub}{pixel}</body></html>')
        msg.add_alternative(html, subtype="html")
        # Attache le logo en inline (related) à la partie HTML
        if logo_path.exists():
            try:
                html_part = msg.get_payload()[-1]   # la partie HTML qu'on vient d'ajouter
                html_part.add_related(logo_path.read_bytes(), "image", "png", cid="logiterrelogo")
            except Exception:
                pass

    # PDF
    pdf_name = f"LOGITERRE_2026_Invitation_{safe_filename(org['short'])}.pdf"
    pdf_path = PDF_DIR / pdf_name
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()
    msg.add_attachment(
        pdf_data,
        maintype="application", subtype="pdf",
        filename=pdf_name,
    )
    return msg, pdf_path


def send_one(org, recipients_to, max_retries=MAX_RETRIES, test_mode=False):
    """Open a fresh SMTP connection, send, close. Retry on transient errors."""
    msg, pdf_path = build_message(org, recipients_to, test_mode=test_mode)
    all_rcpts = list(recipients_to) + list(CC_EMAILS)

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            ctx = ssl._create_unverified_context()
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ctx, timeout=60) as smtp:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(msg, from_addr=FROM_EMAIL, to_addrs=all_rcpts)
            return True, pdf_path, None
        except (smtplib.SMTPServerDisconnected,
                smtplib.SMTPConnectError,
                smtplib.SMTPHeloError,
                TimeoutError, ConnectionResetError) as e:
            last_err = e
            if attempt < max_retries:
                print(f"    Transient error ({e}). Waiting {RETRY_DELAY}s before retry {attempt+1}...")
                time.sleep(RETRY_DELAY)
        except smtplib.SMTPResponseException as e:
            # 4xx = temporary, 5xx = permanent
            last_err = e
            if 400 <= e.smtp_code < 500 and attempt < max_retries:
                print(f"    Temporary 4xx ({e.smtp_code}). Waiting {RETRY_DELAY}s before retry...")
                time.sleep(RETRY_DELAY)
            else:
                break
        except Exception as e:
            last_err = e
            break
    return False, pdf_path, last_err


def human_delay():
    """Sleep between 90 and 180 seconds with a human-looking pattern."""
    d = random.randint(MIN_DELAY, MAX_DELAY)
    mins = d // 60
    secs = d % 60
    print(f"    Waiting {mins}m {secs}s before next email (anti-spam)...")
    time.sleep(d)


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--test", action="store_true",
                   help=f"1 email de test vers {TEST_EMAIL}")
    g.add_argument("--all", action="store_true",
                   help=f"Tous les {len(ACADEMIES)} (DÉCONSEILLÉ : risque blocage)")
    g.add_argument("--batch", type=int, metavar="N",
                   help="N premiers non-envoyés (ex: --batch 25)")
    g.add_argument("--range", nargs=2, type=int, metavar=("START", "END"),
                   help="Index 1-based inclusif (ex: --range 1 25)")
    g.add_argument("--resume", action="store_true",
                   help="Reprendre uniquement les institutions non encore envoyées")
    parser.add_argument("--yes", action="store_true", help="Pas de confirmation")
    args = parser.parse_args()

    log = load_log()

    # Sélection des cibles
    recipient_override = None
    if args.test:
        targets = [ACADEMIES[0]]
        recipient_override = [TEST_EMAIL]
    elif args.all:
        targets = ACADEMIES
    elif args.batch:
        not_sent = [o for o in ACADEMIES if log.get(o["short"], {}).get("status") != "sent"]
        targets = not_sent[:args.batch]
    elif args.range:
        s, e = args.range
        targets = ACADEMIES[s - 1:e]
    elif args.resume:
        targets = [o for o in ACADEMIES if log.get(o["short"], {}).get("status") != "sent"]
    else:
        targets = []

    if not targets:
        print("Rien à envoyer. Tous déjà envoyés ?")
        return

    # Estimation de la durée
    avg_per_email = (MIN_DELAY + MAX_DELAY) / 2 + 5
    eta_sec = avg_per_email * (len(targets) - 1)
    eta_min = eta_sec / 60

    print()
    print("=" * 60)
    print(f"  LOGITERRE 2026 — Envoi optimisé anti-spam")
    print("=" * 60)
    print(f"  Cibles      : {len(targets)} institution(s)")
    print(f"  Délai       : {MIN_DELAY}-{MAX_DELAY}s aléatoire entre emails")
    print(f"  ETA         : ~{eta_min:.0f} minutes ({eta_min/60:.1f}h)")
    print(f"  SMTP        : {SMTP_SERVER}:{SMTP_PORT}")
    print(f"  Expéditeur  : {FROM_EMAIL}")
    print(f"  Reply-To    : {REPLY_TO}")
    print(f"  CC          : {', '.join(CC_EMAILS)}")
    print(f"  Log         : {LOG_FILE}")
    print("=" * 60)

    if not args.test and not args.yes:
        confirm = input("\nLancer ? (yes/no): ").strip().lower()
        if confirm not in ("yes", "y", "oui", "o"):
            print("Annulé.")
            return

    print("\nDémarrage des envois...\n")
    t_start = time.time()

    for i, org in enumerate(targets, 1):
        t0 = time.time()
        to_list = recipient_override if recipient_override else org["emails"]

        print(f"[{i:3d}/{len(targets)}] {org['short']:25s} → {len(to_list)} TO + {len(CC_EMAILS)} CC")
        ok, pdf_path, err = send_one(org, to_list, test_mode=args.test)
        dt = time.time() - t0

        if ok:
            print(f"           ✓ SENT in {dt:.1f}s — PDF: {pdf_path.name}")
            log[org["short"]] = {
                "status":    "sent",
                "to":        to_list,
                "cc":        CC_EMAILS,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "pdf":       pdf_path.name,
            }
        else:
            err_str = f"{type(err).__name__}: {err}" if err else "Unknown"
            print(f"           ✗ FAILED — {err_str}")
            log[org["short"]] = {
                "status":    "failed",
                "error":     err_str,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            # Si on voit ce blocage Hostinger, on s'arrête tout de suite
            if err and "Disabled by user from hPanel" in str(err):
                print("\n!!! COMPTE HOSTINGER BLOQUÉ — arrêt immédiat. Réactivez via hPanel.")
                save_log(log)
                return

        save_log(log)

        if i < len(targets):
            human_delay()

    elapsed = time.time() - t_start
    sent = sum(1 for v in log.values() if v.get("status") == "sent")
    failed = sum(1 for v in log.values() if v.get("status") == "failed")
    print()
    print("=" * 60)
    print("  Résumé")
    print("=" * 60)
    print(f"  Envoyés OK : {sent}")
    print(f"  Échecs     : {failed}")
    print(f"  Durée      : {elapsed/60:.1f} minutes")
    print(f"  Log        : {LOG_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
