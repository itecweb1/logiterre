"""LOGITERRE 2026 — Génération PDF autonome (sans dépendance au plugin local).
Fonctionne en local ET sur Streamlit Cloud (LibreOffice via packages.txt).
Un .docx est un ZIP : on modifie word/document.xml directement, puis LibreOffice → PDF.
"""
import shutil, subprocess, zipfile, re
from pathlib import Path

def find_soffice():
    """Trouve le binaire LibreOffice quel que soit l'OS."""
    for c in ["soffice", "libreoffice",
              "/opt/homebrew/bin/soffice",
              "/Applications/LibreOffice.app/Contents/MacOS/soffice",
              "/usr/bin/soffice", "/usr/bin/libreoffice"]:
        if shutil.which(c) or Path(c).exists():
            return c
    return "soffice"

SOFFICE = find_soffice()

def xml_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))

def patch_docx(src_docx, dst_docx, replacements):
    """Copie le DOCX en remplaçant du texte dans word/document.xml (via zipfile)."""
    with zipfile.ZipFile(src_docx, "r") as zin:
        with zipfile.ZipFile(dst_docx, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                data = zin.read(item)
                if item == "word/document.xml":
                    txt = data.decode("utf-8")
                    for a, b in replacements.items():
                        txt = txt.replace(a, b)
                    data = txt.encode("utf-8")
                zout.writestr(item, data)

def make_invitation_pdf(template_docx, out_pdf, org_name, template_name,
                        tmp_dir="/tmp", timeout=90):
    """Génère un PDF d'invitation personnalisé. Retourne (Path|None, erreur|None)."""
    template_docx = Path(template_docx); out_pdf = Path(out_pdf)
    if out_pdf.exists():
        return out_pdf, None
    if not template_docx.exists():
        return None, f"Template introuvable : {template_docx}"

    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", out_pdf.stem)
    tmp_docx = Path(tmp_dir) / f"{safe}.docx"
    try:
        # 1. DOCX personnalisé (remplace le nom + retire le surlignage jaune)
        patch_docx(template_docx, tmp_docx, {
            template_name: xml_escape(org_name),
            '<w:highlight w:val="yellow"/>': '',
        })
        # 2. Conversion PDF via LibreOffice
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            [SOFFICE, "--headless", "--convert-to", "pdf",
             "--outdir", str(out_pdf.parent), str(tmp_docx)],
            capture_output=True, text=True, timeout=timeout)
        produced = out_pdf.parent / (tmp_docx.stem + ".pdf")
        if produced.exists() and produced != out_pdf:
            produced.rename(out_pdf)
        if out_pdf.exists():
            return out_pdf, None
        return None, f"LibreOffice: {(r.stderr or '')[:120]}"
    except subprocess.TimeoutExpired:
        return None, "LibreOffice timeout"
    except Exception as e:
        return None, str(e)
    finally:
        tmp_docx.unlink(missing_ok=True)
