#!/usr/bin/env python3
"""
LOGITERRE 2026 — Mode PRUDENT pour les 51 institutions restantes.

Stratégie ultra-prudente Hostinger :
  - 1 SEUL email par institution (le principal, généralement info@)
  - Mini-batchs de 5 institutions max par session
  - Délais 120-240 secondes (2-4 minutes) entre emails
  - 2 sessions/jour max recommandé
  - Arrêt immédiat si Hostinger bloque
  - Reprise automatique (--resume)

Usage:
    python3 send_prudent.py --plan          # Voir le plan complet
    python3 send_prudent.py --batch 5       # Envoyer aux 5 prochains
    python3 send_prudent.py --batch 5 --yes # Sans confirmation
    python3 send_prudent.py --status        # Voir l'avancement
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from send_emails import send_one, save_log, load_log, CC_EMAILS
from academies_clean import ACADEMIES

# Délai fixe 2 minutes
PRUDENT_MIN_DELAY = 60
PRUDENT_MAX_DELAY = 60

LOG_FILE = Path("/Users/ayb/Desktop/logiterre-expo/email_log.json")


def primary_email(org):
    """Retourne l'email principal d'une institution (info@ en priorité)."""
    emails = org["emails"]
    # Cherche dans l'ordre de préférence
    preferences = ["info@", "secretariat@", "contact@", "office@", "admin@", "enquir"]
    for pref in preferences:
        for e in emails:
            if e.lower().startswith(pref):
                return e
    return emails[0]  # fallback : le premier


def already_sent_institutions(log):
    """Retourne le set des institutions déjà envoyées (batch initial + priority)."""
    sent = set()
    for key, value in log.items():
        if value.get("status") != "sent":
            continue
        if key.startswith("PRIORITY_"):
            for org in ACADEMIES:
                if key.startswith(f"PRIORITY_{org['short']}_"):
                    sent.add(org["short"])
                    break
        elif key.startswith("PRUDENT_"):
            short = key[len("PRUDENT_"):]
            sent.add(short)
        else:
            sent.add(key)
    return sent


def get_remaining(log):
    """Liste des institutions restantes avec leur email principal."""
    sent = already_sent_institutions(log)
    return [(o, primary_email(o)) for o in ACADEMIES if o["short"] not in sent]


def prudent_delay():
    """Pause longue 2-4 minutes."""
    d = random.randint(PRUDENT_MIN_DELAY, PRUDENT_MAX_DELAY)
    print(f"    Pause prudente {d//60}m {d%60}s avant le prochain email...")
    time.sleep(d)


def show_plan():
    log = load_log()
    remaining = get_remaining(log)
    sent = already_sent_institutions(log)

    print()
    print("=" * 70)
    print("  📋 PLAN PRUDENT — 51 institutions restantes")
    print("=" * 70)
    print(f"\n✅ Déjà envoyé : {len(sent)} institutions")
    print(f"🔄 À envoyer    : {len(remaining)} institutions")
    print(f"\n📋 LISTE D'ENVOI (1 email par institution) :\n")
    for i, (org, email) in enumerate(remaining, 1):
        country = org.get("country", "")
        print(f"   {i:2d}. {org['short']:25s} → {email:50s} [{country}]")
    print()
    print("=" * 70)
    sessions = (len(remaining) + 4) // 5   # 5 par session
    print(f"  Sessions nécessaires : {sessions} (à 5/session)")
    print(f"  Durée par session    : ~15-20 minutes")
    print(f"  Étalement recommandé : 2 sessions/jour → {(sessions+1)//2} jours")
    print("=" * 70)


def show_status():
    log = load_log()
    sent = already_sent_institutions(log)
    remaining = get_remaining(log)
    print()
    print("=" * 70)
    print(f"  📊 STATUT — {len(sent)}/{len(ACADEMIES)} institutions ({len(sent)*100/len(ACADEMIES):.0f}%)")
    print("=" * 70)
    print(f"  ✅ Envoyés   : {len(sent)}")
    print(f"  🔄 Restants  : {len(remaining)} institutions")
    print(f"  📧 Prochains : ", end="")
    print(", ".join(s for s, e in [(o["short"], e) for o, e in remaining[:5]]))
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true", help="Voir le plan complet")
    g.add_argument("--status", action="store_true", help="État de la campagne")
    g.add_argument("--batch", type=int, metavar="N",
                   help="Envoyer aux N prochaines institutions (recommandé : 5)")
    parser.add_argument("--yes", action="store_true", help="Pas de confirmation")
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
        print("🎉 Toutes les institutions ont été envoyées !")
        return

    targets = remaining[:args.batch]
    avg_delay = (PRUDENT_MIN_DELAY + PRUDENT_MAX_DELAY) / 2
    eta = avg_delay * (len(targets) - 1) / 60 + len(targets) * 0.05

    print()
    print("=" * 70)
    print(f"  🛡️  MODE PRUDENT — {len(targets)} envois (sur {len(remaining)} restants)")
    print("=" * 70)
    for i, (org, email) in enumerate(targets, 1):
        print(f"  {i}. {org['short']:25s} → {email}")
    print("=" * 70)
    print(f"  Délais          : {PRUDENT_MIN_DELAY}-{PRUDENT_MAX_DELAY}s aléatoires (2-4 min)")
    print(f"  ETA             : ~{eta:.0f} minutes")
    print(f"  CC              : {', '.join(CC_EMAILS)}")
    print("=" * 70)

    if not args.yes:
        c = input("\nLancer ? (yes/no): ").strip().lower()
        if c not in ("yes", "y", "oui", "o"):
            print("Annulé.")
            return

    print("\nDémarrage...\n")
    t_start = time.time()
    ok_count = 0

    for i, (org, email) in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {org['short']:25s} → {email}")
        org_for_send = {"short": org["short"], "name": org["name"], "emails": [email]}
        ok, pdf_path, err = send_one(org_for_send, [email])

        if ok:
            print(f"           ✓ SENT — PDF: {pdf_path.name}")
            ok_count += 1
            log[f"PRUDENT_{org['short']}"] = {
                "status":    "sent",
                "to":        [email],
                "cc":        CC_EMAILS,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "pdf":       pdf_path.name,
            }
        else:
            err_str = f"{type(err).__name__}: {err}" if err else "Unknown"
            print(f"           ✗ FAILED — {err_str}")
            if err and "Disabled by user from hPanel" in str(err):
                print("\n!!! Hostinger a bloqué — arrêt immédiat. Réactivez via hPanel.")
                save_log(log)
                return

        save_log(log)
        if i < len(targets):
            prudent_delay()

    elapsed = (time.time() - t_start) / 60
    print()
    print("=" * 70)
    print(f"  ✅ {ok_count}/{len(targets)} envoyés en {elapsed:.1f} min")
    new_sent = already_sent_institutions(load_log())
    print(f"  📊 Total campagne : {len(new_sent)}/{len(ACADEMIES)} institutions "
          f"({len(new_sent)*100/len(ACADEMIES):.0f}%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
