"""LOGITERRE 2026 — Validation d'emails avant envoi
Vérifie : syntaxe · domaine MX · jetable · existence boîte (SMTP) · pleine · Spamhaus · blacklist
"""
import re, socket, smtplib
import dns.resolver

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

# Domaines jetables / temporaires connus (échantillon)
DISPOSABLE = {
    "mailinator.com","guerrillamail.com","10minutemail.com","tempmail.com","temp-mail.org",
    "throwaway.email","yopmail.com","trashmail.com","getnada.com","maildrop.cc",
    "fakeinbox.com","sharklasers.com","grr.la","spam4.me","dispostable.com",
    "mailnesia.com","mintemail.com","mytemp.email","tempinbox.com","emailondeck.com",
}

# Préfixes "role account" (acceptables mais signalés)
ROLE_PREFIXES = {"info","contact","admin","noreply","no-reply","postmaster","sales",
                 "support","office","hello","secretariat","secretary","general","enquiries"}

# Caches (évite les requêtes répétées sur le même domaine)
_mx_cache  = {}
_dbl_cache = {}

def _resolver():
    r = dns.resolver.Resolver()
    r.timeout = 4; r.lifetime = 4
    return r

def check_syntax(email):
    return bool(EMAIL_RE.match(email.strip()))

def check_mx(domain):
    """Le domaine a-t-il un serveur de messagerie ? Retourne (bool, info)."""
    domain = domain.lower()
    if domain in _mx_cache:
        return _mx_cache[domain]
    try:
        mx = _resolver().resolve(domain, "MX")
        host = str(mx[0].exchange).rstrip(".")
        res = (True, host)
    except dns.resolver.NXDOMAIN:
        res = (False, "domaine inexistant")
    except dns.resolver.NoAnswer:
        # Pas de MX mais peut-être un A record (fallback mail)
        try:
            _resolver().resolve(domain, "A")
            res = (True, "A-record (pas de MX dédié)")
        except Exception:
            res = (False, "aucun serveur mail")
    except Exception as e:
        res = (None, f"DNS timeout/erreur")  # None = indéterminé
    _mx_cache[domain] = res
    return res

def check_disposable(domain):
    return domain.lower() in DISPOSABLE

def check_role_account(email):
    local = email.split("@")[0].lower()
    return local in ROLE_PREFIXES

def check_spamhaus_dbl(domain):
    """Spamhaus Domain Block List. Retourne (listed: bool|None, codes)."""
    domain = domain.lower()
    if domain in _dbl_cache:
        return _dbl_cache[domain]
    try:
        ans = _resolver().resolve(f"{domain}.dbl.spamhaus.org", "A")
        codes = [str(a) for a in ans]
        # 127.255.255.x = erreur de requête (pas un vrai listing)
        if any(c.startswith("127.255.255.") for c in codes):
            res = (None, "requête bloquée")
        else:
            res = (True, codes)
    except dns.resolver.NXDOMAIN:
        res = (False, [])      # propre
    except Exception:
        res = (None, "indéterminé")
    _dbl_cache[domain] = res
    return res

def get_public_ip():
    """IP publique de l'expéditeur."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        # IP locale → tenter résolution publique via DNS
        if ip.startswith(("192.168.","10.","172.")):
            try:
                import urllib.request
                ip = urllib.request.urlopen("https://api.ipify.org", timeout=4).read().decode().strip()
            except Exception:
                pass
        return ip
    except Exception:
        return None

def check_ip_zen(ip):
    """Vérifie une IP contre Spamhaus ZEN. Retourne (listed, info)."""
    if not ip:
        return None, "IP introuvable"
    try:
        rev = ".".join(reversed(ip.split(".")))
        ans = _resolver().resolve(f"{rev}.zen.spamhaus.org", "A")
        codes = [str(a) for a in ans]
        return True, f"{ip} — 🔴 LISTÉ ({', '.join(codes)})"
    except dns.resolver.NXDOMAIN:
        return False, f"{ip} — ✅ propre"
    except Exception:
        return None, f"{ip} — vérification impossible"

def check_sender_blacklist(smtp_host="smtp.hostinger.com"):
    """Vérifie l'IP du serveur SMTP d'envoi (Hostinger) ET l'IP publique locale.
    C'est l'IP de Hostinger qui envoie réellement les emails."""
    results = {}
    # 1. IP du serveur SMTP (la vraie IP d'envoi)
    try:
        smtp_ip = socket.gethostbyname(smtp_host)
        listed, info = check_ip_zen(smtp_ip)
        results["smtp"] = {"host": smtp_host, "ip": smtp_ip, "listed": listed, "info": info}
    except Exception as e:
        results["smtp"] = {"host": smtp_host, "ip": None, "listed": None,
                           "info": f"résolution impossible"}
    # 2. IP publique locale (informatif)
    pub = get_public_ip()
    if pub and not pub.startswith(("192.168.","10.","172.")):
        listed2, info2 = check_ip_zen(pub)
        results["local"] = {"ip": pub, "listed": listed2, "info": info2}
    return results


# Cache des résultats SMTP (par email)
_smtp_cache = {}

def check_smtp_mailbox(email, helo_host="logiterre-expo.com",
                       from_addr="postmaster@logiterre-expo.com", timeout=10):
    """Vérifie si la boîte mail EXISTE réellement en interrogeant le serveur du destinataire.
    Détecte : existe / n'existe pas / pleine / catch-all / port 25 bloqué.
    Retourne (status, message). status ∈ exists/not_exist/full/catch_all/unknown/blocked."""
    email = email.strip().lower()
    if email in _smtp_cache:
        return _smtp_cache[email]
    domain = email.split("@")[1]

    # MX du domaine
    has_mx, mx_host = check_mx(domain)
    if has_mx is False:
        res = ("not_exist", "Domaine sans serveur mail")
        _smtp_cache[email] = res; return res
    if has_mx is None or not isinstance(mx_host, str) or "." not in mx_host:
        res = ("unknown", "MX indéterminé")
        _smtp_cache[email] = res; return res

    try:
        smtp = smtplib.SMTP(timeout=timeout)
        smtp.connect(mx_host, 25)
        smtp.helo(helo_host)
        smtp.mail(from_addr)
        code, _ = smtp.rcpt(email)

        # Test catch-all : adresse improbable sur le même domaine
        catch = None
        try:
            cc, _ = smtp.rcpt(f"zz-no-such-user-99x@{domain}")
            catch = cc
        except Exception:
            pass
        try: smtp.quit()
        except Exception: pass

        if code in (250, 251):
            if catch in (250, 251):
                res = ("catch_all", "Le serveur accepte TOUTES les adresses (vérif. impossible)")
            else:
                res = ("exists", "Boîte mail confirmée ✅")
        elif code in (550, 551, 553, 521, 510, 511):
            res = ("not_exist", f"Boîte inexistante (code {code})")
        elif code == 552:
            res = ("full", "Boîte mail PLEINE (quota dépassé)")
        elif code in (450, 451, 452, 421):
            res = ("unknown", f"Greylisting / temporaire (code {code})")
        else:
            res = ("unknown", f"Réponse serveur : {code}")

    except smtplib.SMTPServerDisconnected:
        res = ("blocked", "Serveur a coupé (anti-vérification)")
    except (socket.timeout, TimeoutError):
        res = ("blocked", "Timeout — port 25 probablement bloqué par ton FAI")
    except (ConnectionRefusedError, OSError) as e:
        res = ("blocked", "Port 25 bloqué (ton FAI/réseau le filtre)")
    except Exception as e:
        res = ("unknown", f"{type(e).__name__}")

    _smtp_cache[email] = res
    return res


def validate_email_full(email, check_dns=True, check_spamhaus=True, check_smtp=False):
    """Validation complète d'un email.
    Retourne un dict : email, status, level, reason, badges[]"""
    email = email.strip()
    result = {"email": email, "status": "valid", "level": "ok",
              "reason": "", "badges": []}

    # 1. Syntaxe
    if not check_syntax(email):
        result.update(status="invalid", level="error", reason="Format invalide")
        result["badges"].append("❌ Syntaxe")
        return result

    domain = email.split("@")[1].lower()

    # 2. Jetable
    if check_disposable(domain):
        result.update(status="disposable", level="error", reason="Email jetable/temporaire")
        result["badges"].append("🗑️ Jetable")
        return result

    # 3. Role account (info seulement)
    if check_role_account(email):
        result["badges"].append("👥 Compte générique")

    if check_dns:
        # 4. MX
        has_mx, mx_info = check_mx(domain)
        if has_mx is False:
            result.update(status="no_mx", level="error", reason=f"Domaine non-livrable ({mx_info})")
            result["badges"].append("📭 Pas de MX")
            return result
        elif has_mx is None:
            result["badges"].append("⏱️ MX indéterminé")
        else:
            result["badges"].append("📬 MX OK")

    if check_spamhaus:
        # 5. Spamhaus DBL
        listed, codes = check_spamhaus_dbl(domain)
        if listed is True:
            result.update(status="spamhaus", level="error", reason="Domaine sur Spamhaus DBL")
            result["badges"].append("🔴 Spamhaus")
            return result
        elif listed is False:
            result["badges"].append("🛡️ Spamhaus OK")

    if check_smtp:
        # 6. Existence réelle de la boîte (SMTP)
        smtp_status, smtp_msg = check_smtp_mailbox(email)
        if smtp_status == "exists":
            result["badges"].append("✅ Boîte confirmée")
        elif smtp_status == "not_exist":
            result.update(status="not_exist", level="error", reason=smtp_msg)
            result["badges"].append("❌ Boîte inexistante")
            return result
        elif smtp_status == "full":
            result.update(status="full", level="error", reason=smtp_msg)
            result["badges"].append("📦 Boîte pleine")
            return result
        elif smtp_status == "catch_all":
            result["badges"].append("🌀 Catch-all")
        elif smtp_status == "blocked":
            result["badges"].append("🚧 SMTP bloqué")
        else:
            result["badges"].append("⏱️ SMTP indéterminé")

    return result


def validate_batch(emails, check_dns=True, check_spamhaus=True, check_smtp=False, progress_cb=None):
    """Valide une liste d'emails. Retourne la liste des résultats."""
    results = []
    for i, email in enumerate(emails):
        results.append(validate_email_full(email, check_dns, check_spamhaus, check_smtp))
        if progress_cb:
            progress_cb(i+1, len(emails))
    return results
