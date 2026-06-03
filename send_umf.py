#!/usr/bin/env python3
"""
LOGITERRE 2026 — Envoi UMF Annuaire 2023 (150 organisations maritimes Marseille-Fos).

Stratégie :
  - 1 email principal par organisation
  - Délai fixe 2 minutes entre chaque envoi
  - Sessions de 5 organisations recommandées
  - Reprise automatique (log JSON)

Usage:
    python3 send_umf.py --plan          # Voir le plan complet
    python3 send_umf.py --status        # État de la campagne
    python3 send_umf.py --batch 5       # Envoyer aux 5 prochains
    python3 send_umf.py --batch 5 --yes # Sans confirmation
"""

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, '/tmp')
from send_emails import send_one, save_log, load_log, CC_EMAILS
from umf_data import UMF_CONTACTS

PRUDENT_MIN_DELAY = 120
PRUDENT_MAX_DELAY = 120

LOG_FILE = Path("/Users/ayb/Desktop/logiterre-expo/email_log.json")
LOG_PREFIX = "UMF_"


def primary_email(org):
    """Retourne l'email principal (info@ / contact@ en priorité)."""
    emails = org["emails"]
    preferences = ["info@", "contact@", "secretariat@", "direction@", "admin@"]
    for pref in preferences:
        for e in emails:
            if e.lower().startswith(pref):
                return e
    return emails[0]


def already_sent(log):
    """Set des organisations UMF déjà envoyées."""
    return {k[len(LOG_PREFIX):] for k, v in log.items()
            if k.startswith(LOG_PREFIX) and v.get("status") == "sent"}


def get_remaining(log):
    sent = already_sent(log)
    return [(o, primary_email(o)) for o in UMF_CONTACTS if o["short"] not in sent]


def prudent_delay():
    d = random.randint(PRUDENT_MIN_DELAY, PRUDENT_MAX_DELAY)
    print(f"    Pause {d//60}m {d%60}s avant le prochain email...")
    time.sleep(d)


def show_plan():
    log = load_log()
    remaining = get_remaining(log)
    sent = already_sent(log)
    print()
    print("=" * 72)
    print("  📋 PLAN UMF — Annuaire Marseille-Fos 2023")
    print("=" * 72)
    print(f"\n✅ Déjà envoyé : {len(sent)} organisations")
    print(f"🔄 À envoyer    : {len(remaining)} organisations")
    print()
    current_sector = None
    for i, (org, email) in enumerate(remaining, 1):
        s = org.get("sector", "")
        if s != current_sector:
            print(f"\n  ── {s} ──")
            current_sector = s
        print(f"   {i:3d}. {org['short']:28s} → {email}")
    print()
    print("=" * 72)
    sessions = (len(remaining) + 4) // 5
    print(f"  Sessions nécessaires : {sessions} (à 5/session, 2 min entre chaque)")
    print(f"  Durée par session    : ~10 minutes")
    print(f"  Étalement recommandé : 2 sessions/jour → {(sessions+1)//2} jours")
    print("=" * 72)


def show_status():
    log = load_log()
    sent = already_sent(log)
    remaining = get_remaining(log)
    print()
    print("=" * 72)
    print(f"  📊 UMF — {len(sent)}/{len(UMF_CONTACTS)} organisations ({len(sent)*100/len(UMF_CONTACTS):.0f}%)")
    print("=" * 72)
    print(f"  ✅ Envoyés   : {len(sent)}")
    print(f"  🔄 Restants  : {len(remaining)}")
    if remaining:
        print(f"  📧 Prochains : {', '.join(o['short'] for o, _ in remaining[:5])}")
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan",   action="store_true")
    g.add_argument("--status", action="store_true")
    g.add_argument("--batch",  type=int, metavar="N")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if args.plan:
        show_plan()
        return
    if args.status:
        show_status()
        return

    log = load_log()
    remaining = get_remaining(log)
    if not remaining:
        print("🎉 Toutes les organisations UMF ont été envoyées !")
        return

    targets = remaining[:args.batch]
    avg_delay = (PRUDENT_MIN_DELAY + PRUDENT_MAX_DELAY) / 2
    eta = avg_delay * (len(targets) - 1) / 60 + len(targets) * 0.05

    print()
    print("=" * 72)
    print(f"  🚢 MODE UMF — {len(targets)} envois (sur {len(remaining)} restants)")
    print("=" * 72)
    for i, (org, email) in enumerate(targets, 1):
        sector = org.get("sector", "")
        print(f"  {i}. {org['short']:28s} → {email:45s} [{sector}]")
    print("=" * 72)
    print(f"  Délais : {PRUDENT_MIN_DELAY}s fixes | ETA : ~{eta:.0f} min | CC : {', '.join(CC_EMAILS)}")
    print("=" * 72)

    if not args.yes:
        c = input("\nLancer ? (yes/no): ").strip().lower()
        if c not in ("yes", "y", "oui", "o"):
            print("Annulé.")
            return

    print("\nDémarrage...\n")
    t_start = time.time()
    ok_count = 0

    for i, (org, email) in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {org['short']:28s} → {email}")
        org_for_send = {"short": org["short"], "name": org["name"], "emails": [email]}
        ok, pdf_path, err = send_one(org_for_send, [email])

        if ok:
            print(f"           ✓ SENT — PDF: {pdf_path.name}")
            ok_count += 1
            log[f"{LOG_PREFIX}{org['short']}"] = {
                "status":    "sent",
                "to":        [email],
                "cc":        CC_EMAILS,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "pdf":       pdf_path.name,
                "sector":    org.get("sector", ""),
            }
        else:
            err_str = f"{type(err).__name__}: {err}" if err else "Unknown"
            print(f"           ✗ FAILED — {err_str}")
            if err and "Disabled by user from hPanel" in str(err):
                print("\n!!! Hostinger a bloqué — arrêt immédiat.")
                save_log(log)
                return

        save_log(log)
        if i < len(targets):
            prudent_delay()

    elapsed = (time.time() - t_start) / 60
    new_sent = already_sent(load_log())
    print()
    print("=" * 72)
    print(f"  ✅ {ok_count}/{len(targets)} envoyés en {elapsed:.1f} min")
    print(f"  📊 Total UMF : {len(new_sent)}/{len(UMF_CONTACTS)} ({len(new_sent)*100/len(UMF_CONTACTS):.0f}%)")
    print("=" * 72)


if __name__ == "__main__":
    main()
