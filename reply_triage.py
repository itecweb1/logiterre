"""LOGITERRE 2026 — Triage intelligent des réponses + brouillons auto
Classe chaque réponse reçue et génère un brouillon de réponse adapté.
Fonctionne sans API (règles), avec hook optionnel pour un vrai LLM.
"""
import re

# ── Catégories + signaux (FR + EN + ES) ───────────────────────
SIGNALS = {
    "interested": {
        "label": "🟢 Intéressé", "color": "#238636",
        "kw": ["interested","pleased","honored","honoured","delighted","will attend",
               "we will participate","happy to","look forward","confirm our participation",
               "count us in","accept your invitation","with pleasure","glad to",
               "intéressé","ravi","honoré","avec plaisir","nous participerons","heureux de",
               "confirmons notre participation","interesado","encantado","participaremos"],
    },
    "needs_info": {
        "label": "🔵 Demande d'infos", "color": "#1f6feb",
        "kw": ["more information","more details","could you provide","please send",
               "questions","clarify","how much","what is the cost","registration fee",
               "when exactly","where exactly","agenda","programme","program","deadline",
               "plus d'informations","plus de détails","pourriez-vous","quel est le coût",
               "frais","quand","où","ordre du jour","programme","más información","detalles"],
    },
    "not_interested": {
        "label": "🔴 Décline", "color": "#da3633",
        "kw": ["decline","unable to","regret","cannot attend","not able","unfortunately we",
               "will not be able","not possible","not interested","must decline","won't be able",
               "déclinons","regrette","ne pourrons","impossible","ne sommes pas en mesure",
               "pas intéressé","ne participera","no podemos","lamentablemente","declinar"],
    },
    "out_of_office": {
        "label": "🟡 Absence auto", "color": "#d29922",
        "kw": ["out of office","auto-reply","automatic reply","on vacation","on leave",
               "currently away","will be back","absence","return on","annual leave",
               "absent","de retour le","congés","réponse automatique","en vacances",
               "ausente","fuera de la oficina","vacaciones"],
    },
    "forwarded": {
        "label": "🟣 Transféré/Redirigé", "color": "#8957e5",
        "kw": ["forwarded your","forwarded to","appropriate colleague","appropriate person",
               "please contact","redirect","my colleague","the right person","in charge of",
               "transféré","transmis à","collègue","la personne en charge","veuillez contacter",
               "responsable","reenviado","colega","persona adecuada"],
    },
}

def detect_language(text):
    """Détection FR/EN/ES basique."""
    t = text.lower()
    fr = sum(t.count(w) for w in [" le "," la "," les "," nous "," vous "," et "," merci"," cordialement"])
    es = sum(t.count(w) for w in [" el "," los "," gracias"," saludos"," nosotros"])
    en = sum(t.count(w) for w in [" the "," we "," you "," thank"," regards"," best "])
    if fr >= en and fr >= es and fr > 0: return "fr"
    if es >= en and es > 0: return "es"
    return "en"

def classify(subject, body):
    """Classe une réponse. Retourne (catégorie, score, signaux trouvés)."""
    text = f"{subject}\n{body}".lower()
    scores = {}
    found = {}
    for cat, cfg in SIGNALS.items():
        hits = [kw for kw in cfg["kw"] if kw in text]
        if hits:
            scores[cat] = len(hits)
            found[cat] = hits
    if not scores:
        return "other", 0, []
    # out_of_office a priorité si détecté (évite de traiter une absence comme réponse)
    if "out_of_office" in scores:
        return "out_of_office", scores["out_of_office"], found["out_of_office"]
    best = max(scores, key=scores.get)
    return best, scores[best], found.get(best, [])

# ── Brouillons de réponse par catégorie (EN par défaut, FR si détecté) ──
DRAFTS = {
    "interested": {
        "en": ("Re: LOGITERRE 2026 – Delighted to welcome you",
"""Dear {name},

Thank you very much for your positive response — we are truly honored that {org} will join us at LOGITERRE 2026 in Casablanca (20–22 October 2026).

To finalize your participation, may I kindly ask you to confirm:
  • The name(s) and title(s) of your delegate(s)
  • Whether you would be interested in a speaking or panel role
  • Any logistical support you may require (visa letter, accommodation)

You may also complete your registration here: https://linktr.ee/LOGITERRE.PRO

We look forward to welcoming you to Casablanca.

With highest consideration,
LOGITERRE 2026 Organizing Committee
sg@logiterre-expo.com | +212 673 642 4246"""),
        "fr": ("Re: LOGITERRE 2026 – Ravis de vous accueillir",
"""Cher/Chère {name},

Nous vous remercions vivement pour votre réponse positive — c'est un honneur que {org} se joigne à LOGITERRE 2026 à Casablanca (20–22 octobre 2026).

Pour finaliser votre participation, pourriez-vous nous confirmer :
  • Le(s) nom(s) et titre(s) de vos délégué(s)
  • Votre intérêt éventuel pour une intervention ou un panel
  • Tout soutien logistique nécessaire (lettre de visa, hébergement)

Vous pouvez aussi compléter votre inscription ici : https://linktr.ee/LOGITERRE.PRO

Au plaisir de vous accueillir à Casablanca.

Avec nos salutations distinguées,
Comité d'organisation LOGITERRE 2026
sg@logiterre-expo.com | +212 673 642 4246"""),
    },
    "needs_info": {
        "en": ("Re: LOGITERRE 2026 – Information you requested",
"""Dear {name},

Thank you for your interest in LOGITERRE 2026. Please find the key details below:

  • Dates: 20–22 October 2026
  • Venue: Casablanca, Kingdom of Morocco
  • Under the High Patronage of His Majesty King Mohammed VI
  • Participation: by official invitation; no registration fee for invited institutions
  • Full programme & registration: https://linktr.ee/LOGITERRE.PRO

I would be glad to schedule a brief call to answer any further questions and discuss how {org} could best contribute.

With highest consideration,
LOGITERRE 2026 Organizing Committee
sg@logiterre-expo.com | +212 673 642 4246"""),
        "fr": ("Re: LOGITERRE 2026 – Les informations demandées",
"""Cher/Chère {name},

Merci de votre intérêt pour LOGITERRE 2026. Voici les informations essentielles :

  • Dates : 20–22 octobre 2026
  • Lieu : Casablanca, Royaume du Maroc
  • Sous le Haut Patronage de Sa Majesté le Roi Mohammed VI
  • Participation : sur invitation officielle ; aucun frais pour les institutions invitées
  • Programme complet & inscription : https://linktr.ee/LOGITERRE.PRO

Je serais ravi d'organiser un bref échange pour répondre à vos questions et discuter de la contribution de {org}.

Avec nos salutations distinguées,
Comité d'organisation LOGITERRE 2026
sg@logiterre-expo.com | +212 673 642 4246"""),
    },
    "not_interested": {
        "en": ("Re: LOGITERRE 2026 – Thank you",
"""Dear {name},

Thank you for taking the time to reply. We fully understand and respect your decision.

Should circumstances change, the invitation remains open, and we would be honored to welcome {org} at a future edition. We will keep you informed of upcoming opportunities.

With our highest consideration and best wishes,
LOGITERRE 2026 Organizing Committee
sg@logiterre-expo.com"""),
        "fr": ("Re: LOGITERRE 2026 – Merci",
"""Cher/Chère {name},

Nous vous remercions d'avoir pris le temps de nous répondre. Nous comprenons et respectons pleinement votre décision.

Si les circonstances venaient à évoluer, l'invitation reste ouverte et ce serait un honneur d'accueillir {org} lors d'une prochaine édition.

Avec nos salutations distinguées,
Comité d'organisation LOGITERRE 2026
sg@logiterre-expo.com"""),
    },
    "forwarded": {
        "en": ("Re: LOGITERRE 2026 – Thank you for redirecting",
"""Dear {name},

Thank you for kindly forwarding our invitation to the appropriate person within {org}. We greatly appreciate it.

If you could share the contact details of the relevant colleague, we will follow up directly. Your support is sincerely valued.

With highest consideration,
LOGITERRE 2026 Organizing Committee
sg@logiterre-expo.com | +212 673 642 4246"""),
        "fr": ("Re: LOGITERRE 2026 – Merci pour la transmission",
"""Cher/Chère {name},

Nous vous remercions d'avoir transmis notre invitation à la personne concernée au sein de {org}. Nous l'apprécions vivement.

Si vous pouviez nous communiquer les coordonnées du collègue concerné, nous assurerons le suivi directement.

Avec nos salutations distinguées,
Comité d'organisation LOGITERRE 2026
sg@logiterre-expo.com | +212 673 642 4246"""),
    },
    "out_of_office": {
        "en": (None, None),  # pas de réponse à une absence automatique
        "fr": (None, None),
    },
    "other": {
        "en": ("Re: LOGITERRE 2026",
"""Dear {name},

Thank you for your message regarding LOGITERRE 2026. We will review it carefully and revert to you shortly.

For your reference, full details are available here: https://linktr.ee/LOGITERRE.PRO

With highest consideration,
LOGITERRE 2026 Organizing Committee
sg@logiterre-expo.com"""),
        "fr": ("Re: LOGITERRE 2026",
"""Cher/Chère {name},

Merci pour votre message concernant LOGITERRE 2026. Nous l'examinons attentivement et reviendrons vers vous très prochainement.

Pour information, tous les détails sont disponibles ici : https://linktr.ee/LOGITERRE.PRO

Avec nos salutations distinguées,
Comité d'organisation LOGITERRE 2026
sg@logiterre-expo.com"""),
    },
}

def draft_reply(category, name, org, lang="en"):
    """Génère un brouillon de réponse. Retourne (subject, body) ou (None, None)."""
    cat = DRAFTS.get(category, DRAFTS["other"])
    subj, body = cat.get(lang, cat.get("en"))
    if not subj:
        return None, None
    name = name or "Sir / Madam"
    org  = org or "your organization"
    return subj, body.format(name=name, org=org)

def triage(subject, body, sender_name="", org_name=""):
    """Analyse complète d'une réponse. Retourne tout le nécessaire pour l'UI."""
    cat, score, signals = classify(subject, body)
    lang = detect_language(f"{subject} {body}")
    cfg = SIGNALS.get(cat, {"label": "⚪ Autre", "color": "#888"})
    d_subj, d_body = draft_reply(cat, sender_name, org_name, lang)
    return {
        "category": cat,
        "label": cfg["label"],
        "color": cfg["color"],
        "confidence": "élevée" if score >= 2 else ("moyenne" if score == 1 else "faible"),
        "signals": signals[:5],
        "lang": lang,
        "draft_subject": d_subj,
        "draft_body": d_body,
        "auto_reply": d_subj is not None,
    }
