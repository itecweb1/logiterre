#!/usr/bin/env python3
"""
LOGITERRE 2026 — Envoi PRIORITAIRE aux 5 emails haute confiance uniquement.

Envoie l'invitation à UN SEUL email par institution (le plus fiable),
avec délais anti-spam.

Usage:
    python3 send_priority.py            # envoi des 5 (≈ 8-12 min)
    python3 send_priority.py --dry      # simulation sans envoi
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Réutilise toute l'infrastructure du script principal
from send_emails import send_one, human_delay, save_log, load_log, safe_filename, CC_EMAILS, PDF_DIR

# ============================================================
# LISTE PRIORITAIRE (haute confiance ≥ 77 + 3 vérifiés)
# ============================================================
PRIORITY_EMAILS = [
    # 3 emails VÉRIFIÉS VALIDES (score 91-100)
    {"short": "IESE_CIIL", "name": "IESE Business School - Center for International Industrial Logistics (CIIL)",
     "email": "info@iese.edu", "score": 100, "verified": True},
    {"short": "UM6P", "name": "Mohammed VI Polytechnic University (UM6P) - Sustainable Logistics & Territories Chair",
     "email": "contact@um6p.ma", "score": 100, "verified": True},
    {"short": "IESE_CIIL", "name": "IESE Business School - Center for International Industrial Logistics (CIIL)",
     "email": "executiveeducation@iese.edu", "score": 91, "verified": True},

    # 5 emails HAUTE CONFIANCE (score 77-91)
    {"short": "ERTICO", "name": "ERTICO - ITS Europe",
     "email": "info@mail.ertico.com", "score": 91, "verified": False},
    {"short": "ALICE", "name": "ALICE - Alliance for Logistics Innovation through Collaboration in Europe",
     "email": "info@etp-alice.eu", "score": 90, "verified": False},
    {"short": "ITS_Leeds", "name": "Institute for Transport Studies - University of Leeds (ITS Leeds)",
     "email": "info@its.leeds.ac.uk", "score": 84, "verified": False},
    {"short": "AFT_IFTIM_AFTRAL", "name": "AFT-IFTIM / AFTRAL (Apprendre et se Former en Transport et Logistique)",
     "email": "international@aftral.com", "score": 77, "verified": False},
    {"short": "PortXL_Rotterdam", "name": "Port of Rotterdam Authority - PortXL Innovation Hub",
     "email": "innovation@portofrotterdam.com", "score": 77, "verified": False},
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="Simulation sans envoi")
    parser.add_argument("--top5", action="store_true",
                        help="Uniquement les 5 haute confiance (sans les 3 vérifiés)")
    parser.add_argument("--verified", action="store_true",
                        help="Uniquement les 3 vérifiés valides")
    args = parser.parse_args()

    if args.verified:
        targets = [t for t in PRIORITY_EMAILS if t["verified"]]
    elif args.top5:
        targets = [t for t in PRIORITY_EMAILS if not t["verified"]]
    else:
        targets = PRIORITY_EMAILS

    log = load_log()

    print()
    print("=" * 70)
    print("  LOGITERRE 2026 — ENVOI PRIORITAIRE (emails haute confiance)")
    print("=" * 70)
    for i, t in enumerate(targets, 1):
        check = "✓ vérifié" if t["verified"] else "  "
        print(f"  {i}. [{t['score']:3d}%] {check}  {t['email']:45s} ({t['short']})")
    print("=" * 70)
    print(f"  Total       : {len(targets)} emails")
    print(f"  Pièce jointe: PDF personnalisé par institution")
    print(f"  CC          : {', '.join(CC_EMAILS)}")
    avg_delay = 135
    eta = avg_delay * (len(targets) - 1) / 60
    print(f"  ETA         : ~{eta:.0f} minutes")
    print("=" * 70)

    if args.dry:
        print("\n--dry: aucun envoi effectué.")
        return

    print("\nDémarrage des envois...\n")
    t_start = time.time()
    sent_count = 0

    for i, t in enumerate(targets, 1):
        org_for_send = {"short": t["short"], "name": t["name"], "emails": [t["email"]]}
        score_tag = "✓" if t["verified"] else " "
        print(f"[{i}/{len(targets)}] {score_tag}[{t['score']:3d}%] {t['short']:20s} → {t['email']}")

        ok, pdf_path, err = send_one(org_for_send, [t["email"]])

        if ok:
            print(f"           ✓ SENT — PDF: {pdf_path.name}")
            sent_count += 1
            key = f"PRIORITY_{t['short']}_{t['email']}"
            log[key] = {
                "status": "sent",
                "to": [t["email"]],
                "cc": CC_EMAILS,
                "score": t["score"],
                "verified": t["verified"],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "pdf": pdf_path.name,
            }
        else:
            err_str = f"{type(err).__name__}: {err}" if err else "Unknown"
            print(f"           ✗ FAILED — {err_str}")
            if err and "Disabled by user from hPanel" in str(err):
                print("\n!!! COMPTE HOSTINGER BLOQUÉ — arrêt immédiat.")
                save_log(log)
                return

        save_log(log)
        if i < len(targets):
            human_delay()

    elapsed = (time.time() - t_start) / 60
    print()
    print("=" * 70)
    print(f"  Résumé : {sent_count}/{len(targets)} envoyés en {elapsed:.1f} min")
    print("=" * 70)


if __name__ == "__main__":
    main()
