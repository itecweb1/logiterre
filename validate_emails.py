#!/usr/bin/env python3
"""
LOGITERRE 2026 — Validation des emails avant envoi.

Vérifie pour chaque email :
  1) Format (regex RFC)
  2) Présence d'enregistrement MX (domaine accepte du mail)
  3) Liste les domaines uniques pour mise en cache

Génère 3 fichiers :
  - emails_VALIDES.csv      → emails à utiliser
  - emails_INVALIDES.csv    → emails à exclure (avec raison)
  - emails_PAR_INSTITUTION.csv → vue par institution

Usage:
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 validate_emails.py
"""

import csv
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import dns.resolver
import dns.exception

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, '/tmp')
from academies import ACADEMIES

OUT_DIR = Path("/Users/ayb/Desktop/logiterre-expo")

# Format RFC simplifié mais robuste
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)

# Cache des MX par domaine
mx_cache = {}


def check_format(email: str):
    """Vérifie le format de l'email."""
    email = email.strip()
    if not email:
        return False, "Vide"
    if " " in email:
        return False, "Contient un espace"
    if email.count("@") != 1:
        return False, "Manque ou trop de @"
    if not EMAIL_RE.match(email):
        return False, "Format invalide"
    return True, "OK"


def check_mx(domain: str):
    """Vérifie les enregistrements MX du domaine. Retourne (bool, info)."""
    if domain in mx_cache:
        return mx_cache[domain]

    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 10
        answers = resolver.resolve(domain, "MX")
        mx_records = sorted(
            [(r.preference, str(r.exchange).rstrip(".")) for r in answers]
        )
        mx_cache[domain] = (True, mx_records[0][1] if mx_records else "?")
    except dns.resolver.NoAnswer:
        mx_cache[domain] = (False, "Pas d'enregistrement MX")
    except dns.resolver.NXDOMAIN:
        mx_cache[domain] = (False, "Domaine inexistant")
    except dns.resolver.NoNameservers:
        mx_cache[domain] = (False, "Aucun serveur DNS répond")
    except dns.exception.Timeout:
        mx_cache[domain] = (False, "DNS timeout")
    except Exception as e:
        mx_cache[domain] = (False, f"{type(e).__name__}: {e}")

    return mx_cache[domain]


def validate_email(email: str):
    """Validation complète d'un email."""
    email = email.strip()

    # 1) Format
    ok, reason = check_format(email)
    if not ok:
        return False, "format", reason

    # 2) MX
    domain = email.split("@", 1)[1].lower()
    ok, mx = check_mx(domain)
    if not ok:
        return False, "mx", mx

    return True, "valid", mx


def main():
    # Collecter tous les emails uniques
    all_pairs = []  # (institution_short, institution_name, country, email)
    for org in ACADEMIES:
        for email in org["emails"]:
            all_pairs.append({
                "short": org["short"],
                "name": org["name"],
                "country": org.get("country", ""),
                "email": email,
            })

    print(f"📧 Validation de {len(all_pairs)} emails sur "
          f"{len(set(p['email'] for p in all_pairs))} uniques "
          f"({len(set(p['email'].split('@')[1].lower() for p in all_pairs))} domaines)\n")

    valid = []
    invalid = []
    by_inst = defaultdict(list)

    t0 = time.time()
    for i, p in enumerate(all_pairs, 1):
        email = p["email"].strip()
        ok, kind, info = validate_email(email)
        status_icon = "✓" if ok else "✗"
        print(f"[{i:3d}/{len(all_pairs)}] {status_icon} {email:50s} → {info}")

        record = {
            **p,
            "email": email,
            "status": "VALID" if ok else "INVALID",
            "check_type": kind,
            "info": info,
        }
        by_inst[p["short"]].append(record)
        if ok:
            valid.append(record)
        else:
            invalid.append(record)

    elapsed = time.time() - t0
    print(f"\n⏱️  Validé en {elapsed:.1f}s")
    print(f"✅ Valides   : {len(valid)}")
    print(f"❌ Invalides : {len(invalid)}")

    # === Fichier 1 : emails_VALIDES.csv ===
    with open(OUT_DIR / "emails_VALIDES.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["short", "name", "country", "email", "info"])
        w.writeheader()
        for r in valid:
            w.writerow({k: r[k] for k in w.fieldnames})

    # === Fichier 2 : emails_INVALIDES.csv ===
    with open(OUT_DIR / "emails_INVALIDES.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["short", "name", "country", "email", "check_type", "info"])
        w.writeheader()
        for r in invalid:
            w.writerow({k: r[k] for k in w.fieldnames})

    # === Fichier 3 : par institution ===
    with open(OUT_DIR / "emails_PAR_INSTITUTION.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["#", "Short", "Institution", "Country", "Total emails", "Valides", "Invalides", "Détails"])
        for i, org in enumerate(ACADEMIES, 1):
            records = by_inst[org["short"]]
            valid_count = sum(1 for r in records if r["status"] == "VALID")
            invalid_count = sum(1 for r in records if r["status"] == "INVALID")
            details = []
            for r in records:
                mark = "✓" if r["status"] == "VALID" else "✗"
                details.append(f"{mark} {r['email']}")
            w.writerow([
                i, org["short"], org["name"], org.get("country", ""),
                len(records), valid_count, invalid_count,
                " | ".join(details),
            ])

    # === Fichier 4 : nouveau academies.py SANS les emails invalides ===
    valid_emails_by_short = defaultdict(list)
    for r in valid:
        valid_emails_by_short[r["short"]].append(r["email"])

    # Liste des institutions avec au moins 1 email valide
    insts_with_emails = [o for o in ACADEMIES if valid_emails_by_short[o["short"]]]
    insts_no_email = [o for o in ACADEMIES if not valid_emails_by_short[o["short"]]]

    # Sauvegarde dans academies_clean.py
    with open(OUT_DIR / "academies_clean.py", "w", encoding="utf-8") as f:
        f.write("# Académies avec emails validés (générée par validate_emails.py)\n")
        f.write(f"# Validé le {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# {len(insts_with_emails)} institutions, "
                f"{sum(len(valid_emails_by_short[o['short']]) for o in insts_with_emails)} emails valides\n\n")
        f.write("ACADEMIES = [\n")
        for o in insts_with_emails:
            emails = valid_emails_by_short[o["short"]]
            esc_name = o["name"].replace('"', '\\"')
            country = o.get("country", "")
            f.write(f'    {{"short": "{o["short"]}", '
                    f'"name": "{esc_name}", '
                    f'"country": "{country}", '
                    f'"emails": {emails!r}}},\n')
        f.write("]\n")

    print(f"\n📁 Fichiers générés dans {OUT_DIR} :")
    print(f"   - emails_VALIDES.csv         ({len(valid)} lignes)")
    print(f"   - emails_INVALIDES.csv       ({len(invalid)} lignes)")
    print(f"   - emails_PAR_INSTITUTION.csv ({len(ACADEMIES)} lignes)")
    print(f"   - academies_clean.py         ({len(insts_with_emails)} institutions)")
    if insts_no_email:
        print(f"\n⚠️  {len(insts_no_email)} institutions sans aucun email valide :")
        for o in insts_no_email:
            print(f"      - {o['short']}: {o['name']}")


if __name__ == "__main__":
    main()
