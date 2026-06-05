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
# Chemins relatifs au dossier du script (portable local + cloud)
_BASE    = Path(__file__).resolve().parent
PDF_DIR  = _BASE / "PDF_ACADEMIES"
LOG_FILE = _BASE / "email_log.json"
PDF_DIR.mkdir(exist_ok=True)

SUBJECT = "Exploring Participation Opportunities at LOGITERRE 2026."

# Lien public (rendu cliquable + traçable via l'Edge Function `click` si Supabase dispo)
LINKTR_URL = "https://linktr.ee/LOGITERRE"

# Joindre le PDF d'invitation ? (désactivable par campagne via cfg/env ATTACH_PDF=0)
ATTACH_PDF = _os.environ.get("ATTACH_PDF", "1").strip().lower() not in ("0", "false", "no", "")

BODY = """Dear {name},

I hope this message finds you well.

I am reaching out regarding LOGITERRE 2026, the International Forum & Exhibition on Transport, Logistics, Smart Mobility and Sustainable Infrastructure, taking place in Casablanca, Morocco, from 20 to 22 October 2026.

LOGITERRE 2026 will bring together public authorities, international organizations, infrastructure developers, logistics operators, technology providers, investors and industry leaders from across Africa and beyond.

Having noted your company's presence within the sector and participation in major international exhibitions, I believe there may be valuable opportunities for your organization to connect with key stakeholders and explore new business partnerships through LOGITERRE 2026.

We would be pleased to discuss potential participation as an exhibitor, sponsor, speaker or institutional partner.

For more information about the event, please visit:

https://linktr.ee/LOGITERRE

Should you wish to receive the Exhibitor Brochure and Partnership Opportunities, simply reply to this email and our team will be delighted to assist you.

Thank you for your time and consideration.

I look forward to hearing from you.

Kind regards,

EZZAHRAOUI AYOUB
International Relations & Development
LOGITERRE 2026 Organizing Committee
Casablanca, Kingdom of Morocco
Email: sg@logiterre-expo.com
Tel / WhatsApp: +212 673 642 4246.
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


def build_message(org, recipient_emails, test_mode=False, attach_pdf=None):
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

    track_id  = org.get("track_id")
    track_url = globals().get("TRACK_BASE_URL", "")
    app_url   = _os.environ.get("APP_URL", "").rstrip("/")        # URL app cloud (RSVP)
    supa_url  = _os.environ.get("SUPABASE_URL", "").rstrip("/")   # pixel via Edge Function
    org_name  = org.get("name", "")
    to_email  = (recipient_emails[0] if recipient_emails else "")
    import urllib.parse as _up

    # Personnalisation (mail-merge) : {name} {first_name} {org} {email}
    # Personnaliser la salutation supprime aussi la règle SpamAssassin DEAR_SOMETHING
    # (+1.7 pt) déclenchée par « Dear Sir / Madam » — gros gain de délivrabilité.
    _nm = (org_name or "").strip() or "Colleague"
    _first = _nm.split()[0] if _nm.split() else _nm
    def _merge(t):
        if not t: return t
        return (t.replace("{name}", _nm).replace("{first_name}", _first)
                 .replace("{org}", _nm).replace("{email}", to_email))

    # Subject / body : override par-destinataire (auto-template) si fourni, puis personnalisé
    subject = _merge(org.get("subject_override") or SUBJECT)
    if test_mode:
        subject = "[TEST] " + subject
    msg["Subject"] = subject
    body_text = _merge(org.get("body_override") or BODY)

    # Désinscription : app cloud (?unsub=email) si dispo, sinon serveur tracking
    if app_url and to_email:
        unsub_link = f"{app_url}/?{_up.urlencode({'unsub': to_email})}"
    elif track_url and track_id:
        unsub_link = f"{track_url}/u/{track_id}"
    else:
        unsub_link = None

    # En-tête List-Unsubscribe : Gmail/Outlook affichent un bouton natif « Se désabonner »
    # (fort signal anti-spam + désinscription en 1 clic, conforme RGPD/RFC 8058)
    if unsub_link:
        msg["List-Unsubscribe"] = f"<{unsub_link}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    # Pixel d'ouverture : priorité à la fonction Supabase Edge (100% cloud, sans Mac)
    pixel_src = None
    if supa_url and to_email:
        q = _up.urlencode({"email": to_email, "org": org_name})
        pixel_src = f"{supa_url}/functions/v1/pixel?{q}"
    elif track_url and track_id:
        pixel_src = f"{track_url}/pixel/{track_id}.png"

    # Lien linktr.ee : traçable via l'Edge Function `click` (enregistre le clic PUIS redirige 302)
    if supa_url and to_email:
        q = _up.urlencode({"email": to_email, "org": org_name, "to": "linktr"})
        link_target = f"{supa_url}/functions/v1/click?{q}"
    else:
        link_target = LINKTR_URL

    # Texte brut : corps + pied de page de désinscription (sans toucher au corps lui-même)
    pure_body = body_text
    if unsub_link:
        body_text += ("\n\n--------------------------------------------------\n"
                      "LOGITERRE 2026 — International Forum & Exhibition\n"
                      "Transport · Logistics · Smart Mobility — Casablanca, 20-22 October 2026\n"
                      "sg@logiterre-expo.com · +212 673 642 4246\n\n"
                      "You received this email regarding participation in LOGITERRE 2026.\n"
                      f"To stop receiving our communications, unsubscribe here: {unsub_link}")

    msg.set_content(body_text)

    # Version HTML : corps + lien linktr.ee traçable + pixel d'ouverture + désinscription
    if True:
        html_body = pure_body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_body = html_body.replace("\n", "<br>\n")
        # Lien traçable avec texte DESCRIPTIF (pas l'URL brute) — évite le décalage
        # texte/href que Outlook/SmartScreen interprète comme du phishing.
        html_body = html_body.replace(
            LINKTR_URL,
            f'<a href="{link_target}" style="color:#1a5fb4;font-weight:bold;text-decoration:underline;">'
            f'LOGITERRE 2026 — Official Event Page</a>')
        cta = ""
        # Pixel d'ouverture : 1x1 transparent SANS display:none (le contenu caché
        # est un signal anti-spam ; un 1x1 transparent l'est beaucoup moins).
        pixel = (f'<img src="{pixel_src}" width="1" height="1" border="0" alt="" '
                 f'style="width:1px;height:1px;opacity:0;overflow:hidden;">'
                 if pixel_src else "")
        unsub = (
            f'<div style="margin-top:34px;padding-top:18px;border-top:1px solid #e6e6e6;'
            f'text-align:center;font-size:12px;color:#9a9a9a;line-height:1.7;">'
            f'<div style="font-weight:bold;color:#6b6b6b;">LOGITERRE 2026 — International Forum &amp; Exhibition</div>'
            f'Transport · Logistics · Smart Mobility — Casablanca, 20–22 October 2026<br>'
            f'<a href="mailto:sg@logiterre-expo.com" style="color:#9a9a9a;text-decoration:none;">sg@logiterre-expo.com</a>'
            f' · +212 673 642 4246<br><br>'
            f'<span style="color:#b0b0b0;">You received this email regarding participation in '
            f'LOGITERRE 2026.</span><br>'
            f'If you no longer wish to receive our communications, '
            f'<a href="{unsub_link}" style="color:#777;text-decoration:underline;font-weight:bold;">'
            f'unsubscribe here</a>.'
            f'</div>') if unsub_link else ""
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

    # PDF (optionnel) — désactivable par campagne (attach_pdf=False ou ATTACH_PDF=0)
    do_pdf = ATTACH_PDF if attach_pdf is None else bool(attach_pdf)
    if org.get("attach_pdf") is not None:
        do_pdf = bool(org.get("attach_pdf"))
    if not do_pdf:
        return msg, None
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


def send_one(org, recipients_to, max_retries=MAX_RETRIES, test_mode=False, attach_pdf=None):
    """Open a fresh SMTP connection, send, close. Retry on transient errors."""
    msg, pdf_path = build_message(org, recipients_to, test_mode=test_mode, attach_pdf=attach_pdf)
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
