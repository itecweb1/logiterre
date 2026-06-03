"""LOGITERRE 2026 — Vérification authentification email (SPF / DKIM / DMARC)
Le facteur #1 de délivrabilité. Sans ces 3 enregistrements DNS, les emails finissent en spam.
"""
import dns.resolver

def _resolver():
    r = dns.resolver.Resolver()
    r.timeout = 5; r.lifetime = 5
    return r

def _txt(name):
    """Récupère les enregistrements TXT (joints)."""
    try:
        ans = _resolver().resolve(name, "TXT")
        out = []
        for r in ans:
            # dnspython renvoie des chunks bytes
            val = b"".join(r.strings).decode("utf-8", "replace") if hasattr(r, "strings") else str(r)
            out.append(val)
        return out
    except Exception:
        return []

def check_spf(domain):
    """SPF : autorise quels serveurs à envoyer pour ce domaine."""
    records = _txt(domain)
    spf = [r for r in records if r.lower().startswith("v=spf1")]
    if not spf:
        return {"status": "missing", "record": None,
                "msg": "Aucun SPF — les serveurs non autorisés peuvent usurper ton domaine"}
    rec = spf[0]
    # qualité
    soft = "~all" in rec
    hard = "-all" in rec
    quality = "strict (-all)" if hard else ("souple (~all)" if soft else "permissif (?all/+all)")
    return {"status": "ok", "record": rec, "msg": f"SPF présent — politique {quality}"}

def check_dmarc(domain):
    """DMARC : que faire des emails qui échouent SPF/DKIM."""
    records = _txt(f"_dmarc.{domain}")
    dmarc = [r for r in records if r.lower().startswith("v=dmarc1")]
    if not dmarc:
        return {"status": "missing", "record": None,
                "msg": "Aucun DMARC — recommandé pour la délivrabilité et l'anti-usurpation"}
    rec = dmarc[0]
    pol = "none"
    for part in rec.split(";"):
        part = part.strip()
        if part.startswith("p="):
            pol = part[2:].strip()
    quality = {"reject": "stricte (reject) ✅", "quarantine": "modérée (quarantine)",
               "none": "monitoring seulement (p=none)"}.get(pol, pol)
    return {"status": "ok", "record": rec, "msg": f"DMARC présent — politique {quality}"}

# Sélecteurs DKIM courants (Hostinger + génériques)
DKIM_SELECTORS = ["hostingermail", "default", "dkim", "mail", "google", "selector1",
                  "selector2", "k1", "s1", "s2", "smtp", "hs1", "hs2"]

def check_dkim(domain, selectors=None):
    """DKIM : signature cryptographique. On teste les sélecteurs courants."""
    selectors = selectors or DKIM_SELECTORS
    for sel in selectors:
        records = _txt(f"{sel}._domainkey.{domain}")
        dkim = [r for r in records if "v=dkim1" in r.lower() or "k=rsa" in r.lower() or "p=" in r]
        if dkim:
            return {"status": "ok", "selector": sel, "record": dkim[0][:80] + "...",
                    "msg": f"DKIM trouvé (sélecteur : {sel})"}
    return {"status": "unknown", "selector": None, "record": None,
            "msg": "DKIM non trouvé sur les sélecteurs courants (peut exister sous un autre nom)"}

def full_check(domain):
    """Vérification complète d'un domaine d'envoi."""
    domain = domain.strip().lower()
    spf   = check_spf(domain)
    dmarc = check_dmarc(domain)
    dkim  = check_dkim(domain)

    # Score global /100
    score = 0
    if spf["status"] == "ok":   score += 40
    if dkim["status"] == "ok":  score += 30
    if dmarc["status"] == "ok": score += 30
    # bonus politique stricte
    if dmarc.get("record") and "p=reject" in dmarc["record"]:    score = min(score + 0, 100)

    if score >= 90:   verdict = "excellent"
    elif score >= 60: verdict = "correct"
    elif score >= 30: verdict = "faible"
    else:             verdict = "critique"

    return {"domain": domain, "spf": spf, "dkim": dkim, "dmarc": dmarc,
            "score": score, "verdict": verdict}


if __name__ == "__main__":
    import sys, json
    d = sys.argv[1] if len(sys.argv) > 1 else "logiterre-expo.com"
    print(json.dumps(full_check(d), indent=2, ensure_ascii=False))
