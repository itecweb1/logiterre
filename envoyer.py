#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║         LOGITERRE 2026 — Script d'envoi universel            ║
║                                                              ║
║  1. Ajoute tes institutions dans la liste MY_LIST ci-dessous ║
║  2. Lance :  python3 envoyer.py                              ║
║  3. C'est tout !  ✅                                          ║
╚══════════════════════════════════════════════════════════════╝
"""

# ─────────────────────────────────────────────────────────────
#  📋  TA LISTE ICI — ajoute/modifie comme tu veux
# ─────────────────────────────────────────────────────────────
MY_LIST = [
    # FORMAT : ("Nom complet de l'institution", "email@domaine.com"),

    # ── Exemples à remplacer par ta vraie liste ───────────────
    ("MIT Center for Transportation & Logistics",       "ctl-communications@mit.edu"),
    ("Harvard Business School — Supply Chain",          "research@hbs.edu"),
    ("Imperial College London — Transport Strategy",    "enquiries.tsc@imperial.ac.uk"),
    ("FIATA — Intl. Freight Forwarders",                "info@fiata.org"),
    ("World Economic Forum — Supply Chain",             "contact@weforum.org"),
    # … ajoute autant de lignes que tu veux …
]

# ─────────────────────────────────────────────────────────────
#  ⚙️  PARAMÈTRES (ne pas toucher sauf besoin)
# ─────────────────────────────────────────────────────────────
DELAI_ENTRE_EMAILS = 120   # secondes entre chaque envoi (2 minutes)

# ═════════════════════════════════════════════════════════════
#  CODE (ne pas modifier)
# ═════════════════════════════════════════════════════════════
import re, shutil, subprocess, sys, time
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from send_emails import send_one, CC_EMAILS

SKILLS_BASE   = Path("/Users/ayb/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/bccd55b2-d065-4c6e-8c7a-7c6decaeb4a3/1b73a259-8c88-403f-958b-fe58d1224aff/skills/docx")
TEMPLATE_DOCX = BASE_DIR / "DOCX_TEMP_ACAD/LOGITERRE_2026_Invitation_ALICE.docx"
PDF_DIR       = BASE_DIR / "PDF_ACADEMIES"
DOCX_DIR      = BASE_DIR / "DOCX_TEMP_ACAD"
TEMPLATE_NAME = "ALICE - Alliance for Logistics Innovation through Collaboration in Europe"

PYTHON  = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
UNPACK  = str(SKILLS_BASE / "scripts/office/unpack.py")
PACK    = str(SKILLS_BASE / "scripts/office/pack.py")
SOFFICE = str(SKILLS_BASE / "scripts/office/soffice.py")


def safe_fn(s):
    return re.sub(r'[^A-Za-z0-9_-]+', '_', s).strip('_')[:60]


def xml_escape(s):
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def make_pdf(name, short):
    """Génère un PDF personnalisé pour l'institution."""
    out_pdf  = PDF_DIR  / f"LOGITERRE_2026_Invitation_{short}.pdf"
    out_docx = DOCX_DIR / f"LOGITERRE_2026_Invitation_{short}.docx"

    if out_pdf.exists():
        return out_pdf  # déjà généré

    tmp = Path(f"/tmp/envoyer_{short}")
    if tmp.exists():
        shutil.rmtree(tmp)

    subprocess.run([PYTHON, UNPACK, str(TEMPLATE_DOCX), str(tmp)],
                   check=True, capture_output=True)

    doc = tmp / "word" / "document.xml"
    c = doc.read_text("utf-8")
    c = c.replace(TEMPLATE_NAME, xml_escape(name))
    c = c.replace('<w:highlight w:val="yellow"/>', '')
    doc.write_text(c, "utf-8")

    subprocess.run([PYTHON, PACK, str(tmp), str(out_docx),
                    "--original", str(TEMPLATE_DOCX)],
                   check=True, capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)

    subprocess.run([PYTHON, SOFFICE, "--headless", "--convert-to", "pdf",
                    "--outdir", str(PDF_DIR), str(out_docx)],
                   capture_output=True)

    lo_out = PDF_DIR / (out_docx.stem + ".pdf")
    if lo_out.exists() and lo_out != out_pdf:
        lo_out.rename(out_pdf)

    return out_pdf if out_pdf.exists() else None


def main():
    if not MY_LIST:
        print("❌  MY_LIST est vide — ajoute des institutions en haut du script.")
        return

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print(f"║  LOGITERRE 2026 — {len(MY_LIST)} institutions à traiter")
    print("╠══════════════════════════════════════════════════════════════╣")
    for i, (name, email) in enumerate(MY_LIST, 1):
        print(f"║  {i:2d}. {name[:45]:<45}  →  {email[:20]}")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  Délai entre emails : {DELAI_ENTRE_EMAILS}s  |  CC : {', '.join(CC_EMAILS)[:35]}")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    c = input("Lancer ? (oui/non) : ").strip().lower()
    if c not in ("oui", "o", "yes", "y"):
        print("Annulé.")
        return

    print()
    ok = 0
    fail = 0
    t0 = time.time()

    for i, (name, email) in enumerate(MY_LIST, 1):
        short = safe_fn(name)
        print(f"[{i}/{len(MY_LIST)}] {name[:50]}")
        print(f"         Email : {email}")

        # 1. Générer le PDF
        print("         ⏳ Génération PDF...", end=" ", flush=True)
        try:
            pdf = make_pdf(name, short)
            if pdf and pdf.exists():
                print(f"✓ {pdf.name}")
            else:
                print("✗ ECHEC PDF — envoi annulé pour cette institution")
                fail += 1
                continue
        except Exception as e:
            print(f"✗ Erreur PDF : {e}")
            fail += 1
            continue

        # 2. Envoyer l'email
        print("         📧 Envoi...", end=" ", flush=True)
        org = {"short": short, "name": name, "emails": [email]}
        ok_send, pdf_path, err = send_one(org, [email])

        if ok_send:
            print(f"✓ ENVOYÉ")
            ok += 1
        else:
            err_str = f"{type(err).__name__}: {err}" if err else "Erreur inconnue"
            print(f"✗ ECHEC : {err_str}")
            fail += 1
            if err and "Disabled by user from hPanel" in str(err):
                print("\n⛔  Hostinger a bloqué — arrêt. Réactivez via hPanel.")
                break

        # 3. Pause entre envois
        if i < len(MY_LIST):
            print(f"         ⏸  Pause {DELAI_ENTRE_EMAILS}s...\n")
            time.sleep(DELAI_ENTRE_EMAILS)

    elapsed = (time.time() - t0) / 60
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print(f"║  ✅  {ok} envoyés  |  ❌  {fail} échecs  |  ⏱  {elapsed:.1f} min")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


if __name__ == "__main__":
    main()
