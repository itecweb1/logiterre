#!/usr/bin/env python3
"""LOGITERRE 2026 — Platform Pro"""

import re, io, os, sys, time, json, shutil, tempfile, subprocess, threading, csv
import imaplib, email, ssl as ssl_mod
from email.header import decode_header
from pathlib import Path
from collections import Counter

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ── Secrets (Streamlit Cloud) → variables d'environnement ─────
# En local : utilise les valeurs par défaut. Sur le cloud : lit les Secrets.
try:
    for _k in ("SMTP_USER","SMTP_PASSWORD","IMAP_USER","IMAP_PASSWORD","APP_PASSWORD",
               "SUPABASE_URL","SUPABASE_KEY","APP_URL"):
        if _k in st.secrets:
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

import supa  # connecteur base persistante (Supabase) — actif si secrets présents

import db                       # SQLite layer
try:
    import report_gen           # PDF report generator
    HAS_REPORT = True
except Exception:
    HAS_REPORT = False

st.set_page_config(page_title="LOGITERRE 2026", page_icon="🌍",
                   layout="wide", initial_sidebar_state="expanded")

# ── Paths ─────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent
PDF_DIR       = BASE_DIR / "PDF_ACADEMIES"
DOCX_DIR      = BASE_DIR / "DOCX_TEMP_ACAD"
LOG_FILE      = BASE_DIR / "email_log.json"
LISTS_DIR     = BASE_DIR / "saved_lists"
TEMPLATE_DOCX = DOCX_DIR / "LOGITERRE_2026_Invitation_ALICE.docx"
TEMPLATE_NAME = "ALICE - Alliance for Logistics Innovation through Collaboration in Europe"
CTRL_FILE     = Path("/tmp/logiterre_ctrl.json")
LIVE_FILE     = Path("/tmp/logiterre_live.json")

PYTHON  = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
SKILLS  = Path("/Users/ayb/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/bccd55b2-d065-4c6e-8c7a-7c6decaeb4a3/1b73a259-8c88-403f-958b-fe58d1224aff/skills/docx")
UNPACK  = str(SKILLS / "scripts/office/unpack.py")
PACK    = str(SKILLS / "scripts/office/pack.py")
SOFFICE = str(SKILLS / "scripts/office/soffice.py")

for d in [PDF_DIR, DOCX_DIR, LISTS_DIR]: d.mkdir(exist_ok=True)

# ── Logo officiel LogiTerre (data URI pour affichage HTML) ────
LOGO_PATH = BASE_DIR / "logo.png"
def _logo_uri():
    try:
        import base64
        return "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode()
    except Exception:
        return ""
LOGO_URI = _logo_uri()

# ══ PAGE PUBLIQUE RSVP (via ?rsvp=<id>&org=<nom>&email=<email>) ══
# Le bouton "Confirm participation" des emails pointe ici. Aucun mot de passe requis.
_qp = st.query_params

# ── Page publique DÉSINSCRIPTION (via ?unsub=<email>) ──────────
if _qp.get("unsub"):
    email_u = _qp.get("unsub", "")
    done = False
    try:
        if supa.enabled(): supa.add_unsub(email_u, "link"); done = True
    except Exception: pass
    if not done:
        try: db.mark_unsubscribe(email_u, "link"); done = True
        except Exception: pass
    _lg = (f"<img src='{LOGO_URI}' style='max-width:260px;width:65%;margin:0 auto 1rem;display:block;'>"
           if LOGO_URI else "<div style='font-size:2.5rem;text-align:center;'>🌍</div>")
    st.markdown(f"""<div style='max-width:520px;margin:8vh auto;background:#fff;border-radius:20px;
      padding:2.5rem;box-shadow:0 20px 60px rgba(0,0,0,.15);text-align:center;'>
      {_lg}
      <h2 style='color:#1a1a2e;font-family:serif;'>Désinscription confirmée</h2>
      <p style='color:#555;'>L'adresse <b>{email_u}</b> ne recevra plus d'emails de LOGITERRE 2026.
      Nous respectons votre choix.</p>
      <p style='color:#aaa;font-size:.8rem;margin-top:1.5rem;'>LOGITERRE 2026 — sg@logiterre-expo.com</p>
      </div>""", unsafe_allow_html=True)
    st.stop()

if _qp.get("rsvp"):
    org_q   = _qp.get("org", "Votre institution")
    email_q = _qp.get("email", "")
    # Enregistre le CLIC (une fois) — arriver ici = avoir cliqué le bouton
    if not st.session_state.get("click_logged"):
        st.session_state["click_logged"] = True
        try:
            if supa.enabled() and email_q:
                supa.record_click(email_q, org_q, "rsvp")
        except Exception:
            pass
    _logo_html = (f"<img src='{LOGO_URI}' style='max-width:280px;width:70%;margin:0 auto .5rem;display:block;'>"
                  if LOGO_URI else "<div style='text-align:center;font-size:2.5rem;'>🌍</div>")
    st.markdown(f"""<div style='max-width:560px;margin:5vh auto;background:#fff;border-radius:20px;
      padding:2.5rem;box-shadow:0 20px 60px rgba(0,0,0,.15);'>
      {_logo_html}
      <p style='text-align:center;color:#888;margin-top:.3rem;'>International Transport &amp; Logistics Forum<br>
      Casablanca · 20–22 octobre 2026</p>
      <div style='background:#f0eefb;border-radius:10px;padding:.7rem;text-align:center;
      font-weight:600;color:#3d2f8f;margin:1rem 0;'>{org_q}</div></div>""",
      unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,3,1])
    with c2:
        if st.session_state.get("rsvp_done"):
            st.success("✅ Merci ! Votre réponse a bien été enregistrée.")
            st.balloons()
        else:
            with st.form("rsvp_public"):
                resp = st.radio("Votre institution participera-t-elle ?",
                                ["✅ Oui","🤔 Peut-être","❌ Non"], horizontal=True)
                deleg = st.number_input("Nombre de délégués", 0, 50, 1)
                spk = st.checkbox("Nous souhaitons proposer un intervenant")
                note = st.text_area("Message (optionnel)", height=80)
                if st.form_submit_button("Confirmer ma réponse", type="primary", use_container_width=True):
                    rmap = {"✅ Oui":"yes","🤔 Peut-être":"maybe","❌ Non":"no"}
                    saved=False
                    if supa.enabled():
                        try:
                            supa.save_rsvp(org_q, email_q, rmap[resp], deleg, int(spk), note); saved=True
                        except Exception as e:
                            st.error(f"Erreur enregistrement : {e}")
                    if not saved:
                        try:
                            db.save_rsvp(None, org_q, email_q, rmap[resp], deleg, int(spk), note); saved=True
                        except Exception as e:
                            st.error(f"Erreur : {e}")
                    if saved:
                        st.session_state["rsvp_done"]=True
                        st.rerun()
    st.stop()

# ── Login utilisateur + mot de passe ──────────────────────────
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
def _get_users():
    """Dict username→password. Depuis Secrets [users], sinon admin=APP_PASSWORD."""
    users = {}
    try:
        if "users" in st.secrets:
            users = {str(k): str(v) for k, v in dict(st.secrets["users"]).items()}
    except Exception:
        pass
    if not users and APP_PASSWORD:
        users = {"admin": APP_PASSWORD}
    return users

def _check_login():
    users = _get_users()
    if not users:
        return True   # local / non configuré : aucun login
    if st.session_state.get("auth_user"):
        return True
    _lg = (f"<img src='{LOGO_URI}' style='max-width:300px;width:80%;margin:0 auto 1.2rem;display:block;'>"
           if LOGO_URI else "<div style='font-size:2.5rem;'>🌍</div><h2 style='font-family:serif;'>LOGITERRE 2026</h2>")
    st.markdown(f"<div style='max-width:400px;margin:9vh auto 0;text-align:center;'>{_lg}"
                "<p style='color:#888;margin-bottom:.5rem;'>Connexion à la plateforme</p></div>",
                unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login_form"):
            user = st.text_input("👤 Identifiant", placeholder="Identifiant")
            pw   = st.text_input("🔒 Mot de passe", type="password", placeholder="Mot de passe")
            ok   = st.form_submit_button("Se connecter", type="primary", use_container_width=True)
        if ok:
            if user in users and pw == users[user]:
                st.session_state["auth_user"] = user
                st.rerun()
            else:
                st.error("❌ Identifiant ou mot de passe incorrect")
    return False

if not _check_login():
    st.stop()

# ── IMAP config ───────────────────────────────────────────────
IMAP_SERVER   = "imap.hostinger.com"
IMAP_PORT     = 993
IMAP_USER     = os.environ.get("IMAP_USER", "a.zahraoui@logiterre-expo.com")
IMAP_PASSWORD = os.environ.get("IMAP_PASSWORD", "")   # vide si non configuré (jamais en dur)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
DATE_RE  = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}$|^\d{2}[-/]\d{2}[-/]\d{4}$")
NUM_RE   = re.compile(r"^\d+\.?\d*$")
NAME_KW  = ["organisation","organization","org","ltd","company","société","societe",
            "nom","name","institution","entreprise","raison","etablissement"]
EMAIL_KW = ["email","mail","courriel","e-mail","contact"]
EMAIL_PREF = ["info@","contact@","hello@","office@","admin@","secretariat@","secretary@",
              "direction@","research@","general@","international@","global@","press@",
              "communications@","events@","membership@"]

# ══ DESIGN SYSTEM ═════════════════════════════════════════════
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,500;9..144,600&display=swap');

:root{
  --bg:#f5f6f8; --surface:#ffffff; --line:#e6e8ee; --line-soft:#eef0f4;
  --ink:#161821; --ink-2:#3f4453; --muted:#8a90a0;
  --accent:#3d2f8f; --accent-2:#6d5ee0; --accent-soft:#f0eefb;
  --ok:#0f8a4f; --warn:#b9770b; --err:#c8362f;
}

html,body,[class*="css"]{font-family:'Inter',-apple-system,sans-serif;color:var(--ink);}
.stApp{background:var(--bg);}
.block-container{padding-top:2.2rem;max-width:1180px;}

/* ── Hero : éditorial, à gauche, plat ── */
.hero{position:relative;background:var(--surface);border:1px solid var(--line);
  border-radius:18px;padding:1.6rem 1.9rem 1.5rem;margin-bottom:1.6rem;overflow:hidden;}
.hero::before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;
  background:linear-gradient(180deg,var(--accent),var(--accent-2));}
.hero .eyebrow{font-size:.7rem;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
  color:var(--accent-2);margin-bottom:.35rem;}
.hero h1{font-family:'Fraunces',serif;font-size:1.85rem;font-weight:600;margin:0;
  letter-spacing:-.01em;color:var(--ink);}
.hero p{font-size:.92rem;color:var(--muted);margin:.35rem 0 0;max-width:60ch;}

/* ── KPI ── */
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:14px;
  padding:1.15rem 1.25rem;transition:border-color .15s,transform .15s;}
.kpi:hover{border-color:var(--accent-2);transform:translateY(-2px);}
.kpi .k-label{font-size:.68rem;text-transform:uppercase;letter-spacing:.12em;
  color:var(--muted);font-weight:600;}
.kpi .k-val{font-family:'Fraunces',serif;font-size:2.1rem;font-weight:600;
  color:var(--ink);line-height:1.05;margin-top:.15rem;}
.kpi .k-sub{font-size:.72rem;color:var(--muted);margin-top:.15rem;}

/* ── Console ── */
.console{background:#11131a;border-radius:14px;padding:1.2rem 1.3rem;
  font-family:'SF Mono','JetBrains Mono',ui-monospace,monospace;
  font-size:.8rem;color:#9da7c0;min-height:180px;max-height:340px;overflow-y:auto;
  border:1px solid #21242f;line-height:1.75;}
.console .ok{color:#4ade80;} .console .err{color:#f87171;}
.console .info{color:#fbbf24;} .console .dim{color:#5b6172;}

/* ── Progress ── */
.prog-wrap{background:var(--line);border-radius:99px;height:10px;overflow:hidden;margin:.5rem 0;}
.prog-fill{background:linear-gradient(90deg,var(--accent),var(--accent-2));height:100%;
  border-radius:99px;transition:width .5s cubic-bezier(.4,0,.2,1);}

/* ── Pills ── */
.pill-run,.pill-pause,.pill-stop,.pill-done,.pill-idle{
  border-radius:99px;padding:3px 13px;font-size:.74rem;font-weight:600;letter-spacing:.02em;}
.pill-run{background:#e3f6ec;color:#0f8a4f;} .pill-pause{background:#fdf2dc;color:#b9770b;}
.pill-stop{background:#fbe7e5;color:#c8362f;} .pill-done{background:#e3f6ec;color:#0f8a4f;}
.pill-idle{background:#eef0f4;color:#8a90a0;}

/* ── Section title ── */
.section-title{font-size:.78rem;font-weight:700;color:var(--ink-2);letter-spacing:.06em;
  text-transform:uppercase;padding-bottom:.5rem;margin-bottom:.9rem;
  border-bottom:1px solid var(--line);}

/* ── Badges ── */
.badge-sent{background:var(--accent-soft);color:var(--accent);padding:2px 11px;
  border-radius:99px;font-size:.72rem;font-weight:600;}
.badge-new{background:#e6f0ff;color:#1d4ed8;padding:2px 11px;border-radius:99px;font-size:.72rem;font-weight:600;}
.badge-skip{background:#fdf2dc;color:#b9770b;padding:2px 11px;border-radius:99px;font-size:.72rem;font-weight:600;}

/* ── Cards (campagnes etc.) ── */
.lt-card{background:var(--surface);border:1px solid var(--line);border-radius:14px;
  padding:1.1rem 1.3rem;margin-bottom:.7rem;transition:border-color .15s;}
.lt-card:hover{border-color:var(--accent-2);}
.lt-card.active{border-color:var(--accent);background:linear-gradient(0deg,var(--accent-soft),#fff);}
.lt-card .c-title{font-size:1.05rem;font-weight:700;color:var(--ink);}
.lt-card .c-meta{font-size:.78rem;color:var(--muted);margin-top:.35rem;line-height:1.5;}
.lt-card .c-date{font-size:.72rem;color:var(--muted);}

.alert-box{background:#fdf2dc;border-left:3px solid var(--warn);border-radius:10px;
  padding:.8rem 1.1rem;font-size:.87rem;margin:.5rem 0;color:#7a4e08;}
.success-banner{background:var(--accent-soft);border:1px solid var(--accent-2);color:var(--accent);
  border-radius:12px;padding:.9rem 1.4rem;font-weight:600;font-size:.95rem;text-align:center;margin:1rem 0;}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{border-radius:8px 8px 0 0!important;font-weight:600!important;
  font-size:.86rem!important;color:var(--muted)!important;}
.stTabs [aria-selected="true"]{color:var(--accent)!important;}

/* ── Buttons ── */
.stButton>button{border-radius:10px!important;font-weight:600!important;border:1px solid var(--line)!important;
  transition:all .15s!important;}
.stButton>button:hover{border-color:var(--accent-2)!important;transform:translateY(-1px);}
.stButton>button[kind="primary"]{background:var(--accent)!important;border-color:var(--accent)!important;}
.stButton>button[kind="primary"]:hover{background:var(--accent-2)!important;box-shadow:0 6px 18px rgba(61,47,143,.25)!important;}

/* ── Inputs ── */
.stTextInput input,.stTextArea textarea,.stNumberInput input{border-radius:10px!important;
  border:1px solid var(--line)!important;}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:var(--accent-2)!important;
  box-shadow:0 0 0 3px var(--accent-soft)!important;}

/* ── Metrics natives ── */
[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--line);
  border-radius:12px;padding:.9rem 1.1rem;}
[data-testid="stMetricLabel"]{color:var(--muted)!important;}

/* ── Dataframe ── */
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden;border:1px solid var(--line);}

/* ── Sidebar : crème, raffinée ── */
[data-testid="stSidebar"]{background:#15131f!important;border-right:1px solid #262433;}
[data-testid="stSidebar"] *{color:#e7e5f0!important;}
[data-testid="stSidebar"] hr{border-color:#2a2838!important;}
[data-testid="stSidebar"] .stRadio label{padding:.45rem .75rem;border-radius:9px;
  transition:background .12s;font-size:.9rem;}
[data-testid="stSidebar"] .stRadio label:hover{background:rgba(255,255,255,.05);}

#MainMenu,header[data-testid="stHeader"]{background:transparent;}
</style>""", unsafe_allow_html=True)

# ══ HELPERS ═══════════════════════════════════════════════════
import threading as _thr
_LOG_LOCK = _thr.Lock()
_last_ctrl = {"action": "run"}   # dernière action connue (fallback anti-flicker)

import re as _re_md
# FIX récursion : stocke l'ORIGINAL une seule fois sur le module st (persiste entre reruns).
# Sans ce garde, chaque rerun re-wrappait le wrapper → récursion infinie sur le cloud.
if not hasattr(st, "_orig_markdown"):
    st._orig_markdown = st.markdown
def _safe_markdown(body, *a, **k):
    """Dé-indente le HTML multi-ligne (sinon Streamlit le rend en bloc de code)."""
    if k.get("unsafe_allow_html") and isinstance(body, str) and "\n" in body:
        body = _re_md.sub(r"\n[ \t]+", "\n", body)
    return st._orig_markdown(body, *a, **k)
st.markdown = _safe_markdown

def H(s):
    """Rend du HTML proprement (dé-indenté)."""
    st.markdown(s.strip(), unsafe_allow_html=True)

# ── Composants UI réutilisables ───────────────────────────────
def page_header(eyebrow, title, subtitle=""):
    H(f"""<div class="hero"><div class="eyebrow">{eyebrow}</div>
    <h1>{title}</h1>{f'<p>{subtitle}</p>' if subtitle else ''}</div>""")

def kpi(label, value, sub="", accent="var(--accent)"):
    H(f"""<div class="kpi"><div class="k-bar" style="background:{accent};"></div>
    <div class="k-label">{label}</div>
    <div class="k-val">{value}</div>{f'<div class="k-sub">{sub}</div>' if sub else ''}</div>""")

# CSS premium additionnel (composants dashboard)
st.markdown("""<style>
.kpi{position:relative;overflow:hidden;}
.kpi .k-bar{position:absolute;left:0;top:0;height:3px;width:100%;opacity:.85;}

/* Hero band — la vitrine du dashboard */
.heroband{display:grid;grid-template-columns:1.1fr 1fr;gap:0;background:var(--surface);
  border:1px solid var(--line);border-radius:18px;overflow:hidden;margin-bottom:1.1rem;}
.heroband .hb-left{padding:1.7rem 1.9rem;background:
  radial-gradient(120% 140% at 0% 0%, #1b1733 0%, #14152b 55%, #11121f 100%);color:#fff;}
.hb-eyebrow{font-size:.68rem;font-weight:700;letter-spacing:.2em;text-transform:uppercase;
  color:#a99cf0;}
.hb-num{font-family:'Fraunces',serif;font-size:3.4rem;font-weight:600;line-height:1;margin:.3rem 0 .1rem;
  letter-spacing:-.02em;}
.hb-cap{font-size:.85rem;color:#b9bccd;}
.hb-spark{display:flex;align-items:flex-end;gap:3px;height:42px;margin-top:1rem;}
.hb-spark span{flex:1;background:linear-gradient(180deg,#6d5ee0,#3d2f8f);border-radius:3px 3px 0 0;
  min-height:3px;opacity:.9;}
.hb-right{padding:1.7rem 1.9rem;}
.funnel-row{display:flex;align-items:center;gap:.8rem;margin:.55rem 0;}
.funnel-row .fr-lbl{font-size:.78rem;color:var(--ink-2);width:78px;font-weight:600;}
.funnel-row .fr-bar{flex:1;height:9px;background:var(--line);border-radius:99px;overflow:hidden;}
.funnel-row .fr-fill{height:100%;border-radius:99px;}
.funnel-row .fr-val{font-size:.82rem;font-weight:700;color:var(--ink);width:42px;text-align:right;
  font-variant-numeric:tabular-nums;}

/* Feed */
.feed-item{display:flex;align-items:center;justify-content:space-between;padding:.6rem 0;
  border-bottom:1px solid var(--line-soft);}
.feed-item:last-child{border-bottom:none;}
.feed-item .fi-dot{width:7px;height:7px;border-radius:99px;background:var(--accent-2);margin-right:.7rem;flex:none;}
.feed-item .fi-name{font-size:.85rem;font-weight:600;color:var(--ink);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;}
.feed-item .fi-time{font-size:.74rem;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums;}

/* Card générique */
.panel{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1.3rem 1.4rem;}
.panel-title{font-size:.74rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);margin-bottom:.9rem;}

/* Health chip */
.health{display:inline-flex;align-items:center;gap:.5rem;background:var(--surface);
  border:1px solid var(--line);border-radius:99px;padding:.4rem .9rem;font-size:.8rem;font-weight:600;}
.health .dot{width:8px;height:8px;border-radius:99px;}
</style>""", unsafe_allow_html=True)

def _atomic_write(path, text):
    """Écriture atomique : écrit dans un .tmp puis remplace (pas de lecture mi-écriture)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)

def write_ctrl(a):
    _last_ctrl["action"] = a
    try: _atomic_write(CTRL_FILE, json.dumps({"action":a}))
    except: pass
def read_ctrl():
    try:
        a = json.loads(CTRL_FILE.read_text()).get("action","run")
        _last_ctrl["action"] = a
        return a
    except:
        return _last_ctrl.get("action","run")   # dernière action connue, pas "run" forcé
def write_live(d):
    try: _atomic_write(LIVE_FILE, json.dumps(d,ensure_ascii=False,default=str))
    except: pass
def read_live():
    try: return json.loads(LIVE_FILE.read_text())
    except: return {"status":"idle","total":0,"sent":0,"failed":0,"current":"","eta":0,"log":[]}
def load_log():
    if LOG_FILE.exists():
        try: return json.loads(LOG_FILE.read_text())
        except: return {}
    return {}
def append_log_entry(key, value):
    """Écrit une entrée dans email_log.json de façon atomique + thread-safe."""
    with _LOG_LOCK:
        log = load_log()
        log[key] = value
        try: _atomic_write(LOG_FILE, json.dumps(log, indent=2, ensure_ascii=False))
        except: pass

# ── Quota Hostinger : 1 envoi = 1 destinataire + N CC messages ──
PLAN_LIMITS = {
    "Gratuit / Essai — 100/jour":            100,
    "Business Starter — 1 000/jour":         1000,
    "Business Premium — 3 000/jour":         3000,
}

def messages_today():
    """Nombre de MESSAGES envoyés aujourd'hui (chaque destinataire + CC compte).
    C'est l'unité que Hostinger limite. Supabase si dispo (persistant cloud)."""
    if supa.enabled():
        try: return supa.messages_today()
        except Exception: pass
    today = time.strftime("%Y-%m-%d")
    n = 0
    for v in load_log().values():
        if v.get("status") == "sent" and v.get("timestamp", "").startswith(today):
            n += len(v.get("to", []) or [1]) + len(v.get("cc", []) or [])
    return n

# ══ IMAP HELPERS ══════════════════════════════════════════════

def imap_connect():
    """Ouvre une connexion IMAP Hostinger."""
    ctx = ssl_mod._create_unverified_context()
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, ssl_context=ctx)
    mail.login(IMAP_USER, IMAP_PASSWORD)
    return mail

def decode_str(s):
    """Décode un header email (charset peut être None, utf-8, iso-8859-1...)."""
    if s is None: return ""
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try: result.append(part.decode(charset or "utf-8", errors="replace"))
            except: result.append(part.decode("latin-1", errors="replace"))
        else:
            result.append(part)
    return "".join(result)

def get_email_body(msg):
    """Extrait le texte brut d'un email."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                try:
                    b = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body = b.decode(charset, errors="replace")
                    break
                except: pass
    else:
        try:
            b = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body = b.decode(charset, errors="replace")
        except: pass
    return body[:500]

def is_bounce(subject, sender):
    """Détecte les bounces / NDR / échecs de livraison."""
    s = (subject + " " + sender).lower()
    bounce_kw = ["mailer-daemon","delivery failed","undeliverable","bounce",
                 "mail delivery failure","returned mail","delivery status",
                 "failure notice","non-delivery","could not be delivered",
                 "delivery notification","undelivered","postmaster"]
    return any(k in s for k in bounce_kw)

def is_reply_logiterre(subject):
    """Détecte une réponse à nos invitations LOGITERRE."""
    s = subject.lower()
    return any(k in s for k in ["logiterre","re: official invitation","re: invitation",
                                  "forum 2026","casablanca","re: re:"])

def fetch_folder_emails(mail, folder="INBOX", limit=50, search="ALL"):
    """Récupère les N derniers emails d'un dossier."""
    try:
        mail.select(f'"{folder}"' if " " in folder else folder)
        _, data = mail.search(None, search)
        ids = data[0].split()
        ids = ids[-limit:] if len(ids) > limit else ids
        ids = list(reversed(ids))  # plus récents en premier
    except Exception as e:
        return [], str(e)

    emails = []
    for eid in ids:
        try:
            _, msg_data = mail.fetch(eid, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            subject = decode_str(msg.get("Subject", ""))
            sender  = decode_str(msg.get("From", ""))
            date    = decode_str(msg.get("Date", ""))[:25]
            body    = get_email_body(msg)
            bounce  = is_bounce(subject, sender)
            reply   = is_reply_logiterre(subject)
            emails.append({
                "id":      eid.decode(),
                "subject": subject or "(sans objet)",
                "from":    sender,
                "date":    date,
                "body":    body,
                "bounce":  bounce,
                "reply":   reply,
                "tag":     "🔴 Bounce" if bounce else ("💬 Réponse" if reply else "📨 Email"),
            })
        except: pass
    return emails, None

def get_mailbox_stats(mail):
    """Résumé des dossiers principaux."""
    stats = {}
    for folder, label in [("INBOX","Inbox"),("INBOX.Sent","Envoyés"),
                          ("INBOX.Junk","Spam"),("INBOX.Trash","Corbeille")]:
        try:
            mail.select(f'"{folder}"' if " " in folder else folder)
            _, data = mail.search(None, "ALL")
            stats[label] = len(data[0].split()) if data[0] else 0
        except: stats[label] = 0
    return stats
def safe_fn(s): return re.sub(r"[^A-Za-z0-9_-]+","_",s).strip("_")[:60]
def xml_escape(s):
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def total_sent():
    """Nombre total d'emails envoyés. Supabase si dispo (persistant cloud)."""
    if supa.enabled():
        try: return len(supa.get_sent())
        except Exception: pass
    return sum(1 for v in load_log().values() if v.get("status")=="sent")

def already_sent_emails():
    """Set de tous les emails déjà envoyés. Supabase si dispo (persistant cloud)."""
    if supa.enabled():
        try: return supa.sent_emails_set()
        except Exception: pass
    log=load_log()
    sent=set()
    for v in log.values():
        if v.get("status")=="sent":
            for e in v.get("to",[]):
                sent.add(e.lower().strip())
    return sent

# ── Agrégation d'engagement (ouvreurs / cliqueurs / désinscrits) ──
def engagement_data():
    """Construit une vue unifiée par email : envoyé → ouvert → cliqué → répondu / désinscrit.
    Source Supabase si dispo (persistant cloud), sinon log local + SQLite.
    Retourne (rows, stats)."""
    rows = {}          # email -> dict
    def _slot(email, org=""):
        e = (email or "").lower().strip()
        if not e: return None
        if e not in rows:
            rows[e] = {"email": e, "org": org or "", "sent": False, "sent_at": "",
                       "opens": 0, "open_at": "", "clicks": 0, "click_at": "",
                       "replied": False, "response": "", "delegates": 0,
                       "unsub": False, "unsub_reason": ""}
        if org and not rows[e]["org"]:
            rows[e]["org"] = org
        return rows[e]

    if supa.enabled():
        try: sent_l = supa.get_sent()
        except Exception: sent_l = []
        try: opens_l = supa.get_opens()
        except Exception: opens_l = []
        try: clicks_l = supa.get_clicks()
        except Exception: clicks_l = []
        try: rsvp_l = supa.get_rsvps()
        except Exception: rsvp_l = []
        try: unsub_l = supa.get_unsubs()
        except Exception: unsub_l = []
        for s in sent_l:
            r = _slot(s.get("email",""), s.get("org_name",""))
            if r: r["sent"]=True; r["sent_at"]=r["sent_at"] or (s.get("sent_at","") or "")[:16]
        for o in opens_l:
            r = _slot(o.get("email",""), o.get("org_name",""))
            if r:
                r["opens"]+=1
                t=(o.get("created","") or "")[:16]
                if t and (not r["open_at"] or t<r["open_at"]): r["open_at"]=t
        for c in clicks_l:
            r = _slot(c.get("email",""), c.get("org_name",""))
            if r:
                r["clicks"]+=1
                t=(c.get("created","") or "")[:16]
                if t and (not r["click_at"] or t<r["click_at"]): r["click_at"]=t
        for v in rsvp_l:
            r = _slot(v.get("email",""), v.get("org_name",""))
            if r:
                r["replied"]=True; r["response"]=v.get("response","") or ""
                try: r["delegates"]=int(v.get("delegates",0) or 0)
                except Exception: pass
        for u in unsub_l:
            r = _slot(u.get("email",""))
            if r: r["unsub"]=True; r["unsub_reason"]=u.get("reason","") or ""
    else:
        # Fallback local : log global + SQLite
        for k,v in load_log().items():
            if v.get("status")=="sent":
                for e in v.get("to",[]):
                    r=_slot(e, lookup_name(e))
                    if r: r["sent"]=True; r["sent_at"]=r["sent_at"] or (v.get("timestamp","") or "")[:16]
        try:
            for o in db.get_opens():
                r=_slot(o.get("email",""), o.get("name","") or o.get("org_name",""))
                if r: r["opens"]+=1; r["open_at"]=r["open_at"] or (o.get("opened_at","") or "")[:16]
        except Exception: pass
        try:
            for v in db.get_rsvps():
                r=_slot(v.get("email",""), v.get("org_name",""))
                if r: r["replied"]=True; r["response"]=v.get("response","") or ""
        except Exception: pass
        try:
            for u in db.get_unsubscribes():
                r=_slot(u.get("email",""))
                if r: r["unsub"]=True; r["unsub_reason"]=u.get("reason","") or ""
        except Exception: pass

    # Score + grade
    def _grade(r):
        if r["unsub"]:   return (0,  "🚫 Désinscrit",  "#c8362f")
        if r["replied"] and (r["response"]=="yes"):
                          return (100,"🔥 Confirmé",     "#0f8a4f")
        if r["replied"]: return (85, "🔥 A répondu",    "#0f8a4f")
        if r["clicks"]>0:return (70, "🔥 Chaud (cliqué)","#d2691e")
        if r["opens"]>0: return (40, "🌤️ Tiède (ouvert)","#d29922")
        if r["sent"]:    return (10, "❄️ Froid (envoyé)","#5a6472")
        return (0, "—", "#888")
    out=[]
    for r in rows.values():
        sc,lbl,clr = _grade(r)
        r=dict(r); r["score"]=sc; r["grade"]=lbl; r["color"]=clr
        out.append(r)
    out.sort(key=lambda x:(-x["score"], x["org"] or "z"))

    n_sent=sum(1 for r in out if r["sent"])
    n_open=sum(1 for r in out if r["opens"]>0)
    n_click=sum(1 for r in out if r["clicks"]>0)
    n_reply=sum(1 for r in out if r["replied"])
    n_yes=sum(1 for r in out if r["replied"] and r["response"]=="yes")
    n_unsub=sum(1 for r in out if r["unsub"])
    n_deleg=sum(r["delegates"] for r in out if r["replied"] and r["response"]=="yes")
    stats={"contacts":len(out),"sent":n_sent,"open":n_open,"click":n_click,
           "reply":n_reply,"yes":n_yes,"unsub":n_unsub,"deleg":n_deleg,
           "open_rate":round(n_open*100/max(n_sent,1)),
           "click_rate":round(n_click*100/max(n_sent,1)),
           "reply_rate":round(n_reply*100/max(n_sent,1)),
           "ctr":round(n_click*100/max(n_open,1))}
    return out, stats

# ── Org database ──────────────────────────────────────────────
_ORG_DB={}
def _build_org_db():
    global _ORG_DB
    if _ORG_DB: return
    try:
        from academies_clean import ACADEMIES
        for o in ACADEMIES:
            for e in o.get("emails",[]):
                _ORG_DB[e.lower()]=o["name"]
                d=e.lower().split("@")[-1]
                if d not in _ORG_DB: _ORG_DB[d]=o["name"]
    except: pass

def lookup_name(email):
    _build_org_db()
    e=email.lower().strip()
    if e in _ORG_DB: return _ORG_DB[e]
    d=e.split("@")[-1]
    return _ORG_DB.get(d,"")

def is_domain_name(name):
    s=name.strip()
    return len(s)<=15 and " " not in s and s==s.capitalize()

def name_from_domain(email):
    try:
        base=email.split("@")[1].split(".")[0]
        known={"gmail":"Gmail","yahoo":"Yahoo","hotmail":"Hotmail","outlook":"Outlook"}
        return known.get(base,base.replace("-"," ").replace("_"," ").title())
    except: return ""

def best_email(emails):
    if not emails: return None
    if len(emails)==1: return emails[0]
    el=[e.lower() for e in emails]
    for pf in EMAIL_PREF:
        for e in el:
            if e.startswith(pf): return e
    for e in el:
        lc=e.split("@")[0]
        if "." not in lc and "_" not in lc: return e
    return el[0]

def is_valid_name(val):
    s=str(val).strip()
    if len(s)<3: return False
    if NUM_RE.match(s) or DATE_RE.match(s) or EMAIL_RE.search(s): return False
    if s.lower() in ("nan","none","n/a","null","true","false"): return False
    if re.match(r"^[\d\s\-/.:,;]+$",s): return False
    return True

def validate_email(email):
    """Vérifie le format de l'email."""
    return bool(EMAIL_RE.fullmatch(email.strip()))

# ── Extraction ────────────────────────────────────────────────
def _parse_orgs(org_emails):
    results=[]
    sent=already_sent_emails()
    for n,es in org_emails.items():
        chosen=best_email(es)
        if not chosen: continue
        final=n
        if is_domain_name(n) or not n:
            db=lookup_name(chosen)
            if db: final=db
        status="✅ Déjà envoyé" if chosen in sent else "🆕 Nouveau"
        results.append({"✅ Sélect.": chosen not in sent,
                        "name":final,"email":chosen,
                        "tous_emails":" | ".join(es),"statut":status})
    return results

def extract_from_xlsx(file_bytes):
    try:
        df_h=pd.read_excel(io.BytesIO(file_bytes),dtype=str)
        cs=" ".join(str(c).lower() for c in df_h.columns)
        has=any(k in cs for k in NAME_KW+EMAIL_KW+["ltd","organisation","organization"])
        df=df_h if has else pd.read_excel(io.BytesIO(file_bytes),header=None,dtype=str)
    except:
        df=pd.read_excel(io.BytesIO(file_bytes),header=None,dtype=str)
    nc=ec=None
    for col in df.columns:
        cl=str(col).lower()
        if any(k in cl for k in EMAIL_KW) and ec is None: ec=col
        if any(k in cl for k in NAME_KW)  and nc is None: nc=col
    ces={c:sum(1 for v in df[c].dropna().astype(str) if EMAIL_RE.search(v)) for c in df.columns}
    cns={c:sum(1 for v in df[c].dropna().astype(str) if is_valid_name(v) and not EMAIL_RE.search(v)) for c in df.columns}
    if ec is None: ec=max(ces,key=ces.get) if ces else None
    if nc is None: nc=max(cns,key=cns.get) if cns else None
    if ec==nc:
        sn=sorted(cns,key=cns.get,reverse=True); nc=sn[1] if len(sn)>1 else None
    org_emails={}; seen=set()
    for _,row in df.iterrows():
        rs=" ".join(str(v) for v in row if pd.notna(v))
        emails=[e.lower().strip() for e in EMAIL_RE.findall(rs)]
        if not emails: continue
        name=""
        if nc is not None and pd.notna(row.get(nc,"")):
            c=str(row[nc]).strip(); name=c if is_valid_name(c) else ""
        if not name:
            av=[str(v).strip() for v in row if pd.notna(v) and str(v).strip() not in ("nan","")]
            nc2=sorted([v for v in av if is_valid_name(v)],key=len,reverse=True)
            name=nc2[0] if nc2 else ""
        key=name if name else name_from_domain(emails[0])
        if key not in org_emails: org_emails[key]=[]
        for e in emails:
            if e not in seen: seen.add(e); org_emails[key].append(e)
    return _parse_orgs(org_emails)

def extract_from_csv(file_bytes):
    try:
        text=file_bytes.decode("utf-8-sig")
        reader=csv.DictReader(io.StringIO(text))
        rows=list(reader)
    except:
        text=file_bytes.decode("latin-1")
        reader=csv.DictReader(io.StringIO(text))
        rows=list(reader)
    org_emails={}; seen=set()
    for row in rows:
        vals=list(row.values())
        rs=" ".join(str(v) for v in vals)
        emails=[e.lower().strip() for e in EMAIL_RE.findall(rs)]
        if not emails: continue
        name_candidates=[str(v).strip() for v in vals if is_valid_name(str(v))]
        name_candidates.sort(key=len,reverse=True)
        name=name_candidates[0] if name_candidates else ""
        key=name if name else name_from_domain(emails[0])
        if key not in org_emails: org_emails[key]=[]
        for e in emails:
            if e not in seen: seen.add(e); org_emails[key].append(e)
    return _parse_orgs(org_emails)

def extract_from_docx(file_bytes):
    tmp=Path(tempfile.mktemp(suffix=".docx")); tmp.write_bytes(file_bytes)
    tmp2=Path(tempfile.mkdtemp())
    try:
        subprocess.run([PYTHON,UNPACK,str(tmp),str(tmp2)],capture_output=True,check=True)
        import xml.etree.ElementTree as ET
        ns="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        doc=tmp2/"word"/"document.xml"
        root=ET.parse(doc).getroot()
        lines=["".join(t.text for t in p.iter(f"{{{ns}}}t") if t.text).strip()
               for p in root.iter(f"{{{ns}}}p")]
    finally:
        # #3f FIX : nettoyage garanti même en cas d'erreur
        shutil.rmtree(tmp2,ignore_errors=True); tmp.unlink(missing_ok=True)
    org_emails={}; seen=set()
    for line in [l for l in lines if l]:
        emails=[e.lower().strip() for e in EMAIL_RE.findall(line)]
        if not emails: continue
        name=EMAIL_RE.sub("",line).replace("/","").replace(";","").strip(" ,-")
        key=name if is_valid_name(name) else name_from_domain(emails[0])
        if key not in org_emails: org_emails[key]=[]
        for e in emails:
            if e not in seen: seen.add(e); org_emails[key].append(e)
    return _parse_orgs(org_emails)

def extract_from_text(text):
    """Extraction depuis texte brut ou liste d'emails."""
    org_emails={}; seen=set()
    for line in text.splitlines():
        line=line.strip()
        if not line: continue
        emails=[e.lower().strip() for e in EMAIL_RE.findall(line)]
        if not emails: continue
        name=EMAIL_RE.sub("",line).replace(","," ").replace(";"," ").strip()
        key=name if is_valid_name(name) else name_from_domain(emails[0])
        if key not in org_emails: org_emails[key]=[]
        for e in emails:
            if e not in seen: seen.add(e); org_emails[key].append(e)
    return _parse_orgs(org_emails)

def make_pdf(name, short):
    """Génère le PDF d'invitation — méthode autonome (portable local + cloud)."""
    out_pdf=PDF_DIR/f"LOGITERRE_2026_Invitation_{short}.pdf"
    try:
        import pdf_gen
        return pdf_gen.make_invitation_pdf(TEMPLATE_DOCX, out_pdf, name, TEMPLATE_NAME)
    except Exception as e:
        return None, str(e)

# ── Save/Load contact lists (local) ───────────────────────────
def save_list(name, rows):
    p=LISTS_DIR/f"{safe_fn(name)}.json"
    p.write_text(json.dumps({"name":name,"rows":rows,"saved":time.strftime("%Y-%m-%d %H:%M")},
                             ensure_ascii=False,indent=2))

def load_saved_lists():
    return sorted(LISTS_DIR.glob("*.json"),key=lambda x:x.stat().st_mtime,reverse=True)

# ── Stockage unifié des listes : Supabase (persistant cloud) sinon local ──
def list_store_save(name, rows):
    """Sauvegarde une liste par nom. Supabase si dispo (survit aux redéploiements)."""
    name=(name or "").strip()
    if not name: return False
    rows=[dict(r) for r in rows]
    if supa.enabled():
        try: supa.save_list(name, rows); return True
        except Exception: pass
    save_list(name, rows)   # repli local
    return True

def list_store_load():
    """Retourne [{name, rows, saved}] depuis Supabase si dispo, sinon disque local."""
    if supa.enabled():
        try:
            out=[]
            for r in supa.get_lists():
                out.append({"name": r.get("name",""), "rows": r.get("rows") or [],
                            "saved": (r.get("saved") or (r.get("created","") or "")[:16])})
            return out
        except Exception: pass
    out=[]
    for p in load_saved_lists():
        try: d=json.loads(p.read_text())
        except Exception: continue
        out.append({"name": d.get("name",p.stem), "rows": d.get("rows",[]),
                    "saved": d.get("saved","")})
    return out

def list_store_delete(name):
    """Supprime une liste par nom (Supabase + local pour être sûr)."""
    if supa.enabled():
        try: supa.delete_list(name)
        except Exception: pass
    p=LISTS_DIR/f"{safe_fn(name)}.json"
    if p.exists():
        try: p.unlink()
        except Exception: pass

def list_store_names():
    """Set des noms de bases existantes (pour détecter les collisions)."""
    return {d["name"] for d in list_store_load()}

def list_store_rename(old, new):
    """Renomme une base. Retourne (ok, message)."""
    old=(old or "").strip(); new=(new or "").strip()
    if not new: return False, "Nom vide."
    if new==old: return True, "Inchangé."
    if new in list_store_names(): return False, f"Le nom «{new}» existe déjà."
    if supa.enabled():
        try:
            supa.rename_list(old, new); return True, f"Renommé en «{new}»."
        except Exception as e:
            return False, f"Erreur : {str(e)[:80]}"
    # local : relire, réécrire sous le nouveau nom, supprimer l'ancien
    op=LISTS_DIR/f"{safe_fn(old)}.json"
    rows=[]
    if op.exists():
        try: rows=json.loads(op.read_text()).get("rows",[])
        except Exception: pass
    save_list(new, rows)
    if op.exists():
        try: op.unlink()
        except Exception: pass
    return True, f"Renommé en «{new}»."

# ── Warmup : limite d'envoi du jour selon la montée en charge ──
def warmup_today_limit():
    """Limite d'envois pour aujourd'hui selon le warmup (Supabase). None si inactif."""
    if not supa.enabled(): return None
    try:
        w = supa.get_warmup()
    except Exception:
        return None
    if not w or not w.get("active") or not w.get("start_date"): return None
    import datetime as _dt
    try:
        start = _dt.date.fromisoformat(str(w["start_date"])[:10])
    except Exception:
        return None
    days = max(0, (_dt.date.today() - start).days)
    base = int(w.get("day0_limit", 20) or 20)
    return max(1, round(base * (1.5 ** days)))

# ══ BACKGROUND SENDER ════════════════════════════════════════
def send_background(targets, cfg, test_email=None):
    try:
        import send_emails as se
        se.SUBJECT   =cfg["subject"]
        se.BODY      =cfg.get("body", se.BODY)          # corps édité dans le Composer (était ignoré avant)
        se.FROM_NAME =cfg["from_name"]
        se.FROM_EMAIL=cfg["from_email"]
        se.REPLY_TO  =cfg["reply_to"]
        se.CC_EMAILS =[x.strip() for x in cfg["cc"].split(",") if x.strip()]
        se.TRACK_BASE_URL = cfg.get("track_url","").rstrip("/")
        se.ATTACH_PDF = bool(cfg.get("attach_pdf", False))   # joindre le PDF ? (par campagne)
        # Serveur SMTP configurable (par défaut Hostinger) — permet un ESP dédié
        if cfg.get("smtp_server"):   se.SMTP_SERVER = cfg["smtp_server"].strip()
        if cfg.get("smtp_port"):
            try: se.SMTP_PORT = int(cfg["smtp_port"])
            except Exception: pass
        if cfg.get("smtp_user"):     se.SMTP_USER = se.FROM_EMAIL = cfg["smtp_user"].strip()
        if cfg.get("smtp_from"):     se.FROM_EMAIL = cfg["smtp_from"].strip()
        if cfg.get("smtp_password"): se.SMTP_PASSWORD = cfg["smtp_password"]
    except Exception as e:
        write_live({"status":"stopped","total":0,"sent":0,"failed":0,"current":"",
                    "eta":0,"log":[{"ts":"--:--","status":"err","msg":f"❌ Module SMTP : {e}"}]})
        return

    # Campagne DB pour tracking + relances
    track_on    = bool(cfg.get("track_url","").strip())
    followup_on = cfg.get("followup_enabled", False)
    followup_days = cfg.get("followup_days", 7)
    auto_tpl    = cfg.get("auto_template", False)
    # #1 FIX : campaign_id résolu sur le thread principal et passé via cfg (pas de st.session_state ici)
    camp_id = None
    if not test_email and (track_on or followup_on):
        try:
            camp_id = cfg.get("campaign_id") or db.get_default_campaign()
        except: camp_id = None

    # Liste de suppression (bounces/plaintes/manuel) — précalculée une fois
    _suppressed = supa.suppressed_set() if supa.enabled() else set()

    live={"status":"running","total":len(targets),"sent":0,"failed":0,"skipped":0,
          "current":"","eta":len(targets)*cfg["delay"],"log":[],"start":time.time()}
    write_live(live); write_ctrl("run")
    delay=cfg["delay"]

    # ── Envoi programmé : attend l'heure prévue ───────────────
    scheduled = cfg.get("scheduled_ts")
    if scheduled and not test_email:
        live["status"]="scheduled"
        while time.time() < scheduled:
            if read_ctrl()=="stop": live["status"]="stopped"; write_live(live); return
            remain=int(scheduled-time.time())
            live["current"]=f"⏰ Envoi programmé dans {remain//3600}h {(remain%3600)//60}m {remain%60}s"
            live["eta"]=remain+len(targets)*delay
            write_live(live); time.sleep(2)
        live["status"]="running"; write_live(live)

    for i,row in enumerate(targets):
        while True:
            ctrl=read_ctrl()
            if ctrl=="stop": live["status"]="stopped"; write_live(live); return
            if ctrl=="run": break
            live["status"]="paused"; write_live(live); time.sleep(1)

        live["status"]="running"
        # #3a FIX : accès sûr (jamais de KeyError ni TypeError sur nan)
        def _clean(v):
            s=str(v).strip()
            return "" if s.lower() in ("nan","none","nat","") else s
        name=_clean(row.get("name",""))
        email=test_email if test_email else _clean(row.get("email",""))
        if not email:
            live["skipped"]=live.get("skipped",0)+1
            live["log"].insert(0,{"ts":time.strftime("%H:%M:%S"),"status":"dim",
                "msg":f"⏭️ Ligne ignorée (email vide)"})
            write_live(live); continue
        if not name: name=email.split("@")[0]
        short=safe_fn(name) or "contact"
        live["current"]=f"[{i+1}/{len(targets)}] {name[:38]} → {email}"
        live["eta"]=(len(targets)-i)*delay
        write_live(live)
        ts=time.strftime("%H:%M:%S")

        # Garde-fou quota Hostinger : stoppe avant de dépasser la limite/jour
        if cfg.get("daily_guard") and not test_email:
            cc_n=len([x for x in cfg.get("cc","").split(",") if x.strip()])
            per_send=1+cc_n                       # 1 destinataire + N CC = N+1 messages
            limit=cfg.get("plan_limit",100)
            _wl=warmup_today_limit()              # warmup : plafond progressif du jour
            if _wl is not None: limit=min(limit,_wl)
            if messages_today()+per_send > limit:
                live["status"]="stopped"
                live["log"].insert(0,{"ts":ts,"status":"err",
                    "msg":f"🛑 Quota Hostinger atteint ({messages_today()}/{limit} messages aujourd'hui). "
                          f"Arrêt pour protéger le compte. Reprends demain."})
                write_live(live); return

        # Validate email — syntaxe + (optionnel) MX/Spamhaus
        if not validate_email(email):
            live["failed"]+=1
            live["log"].insert(0,{"ts":ts,"status":"err","msg":f"❌ Email invalide : {email}"})
            write_live(live); continue
        if cfg.get("validate_before_send") and not test_email:
            try:
                import email_validator as ev
                # #6 FIX : MX seulement dans la boucle (pas Spamhaus, trop lent) — Spamhaus = page dédiée
                vres=ev.validate_email_full(email, check_dns=True, check_spamhaus=False)
                if vres["level"]=="error":
                    live["failed"]+=1
                    bad=vres["badges"][-1] if vres["badges"] else vres["reason"]
                    live["log"].insert(0,{"ts":ts,"status":"err",
                        "msg":f"🛡️ Bloqué ({vres['status']}) : {name[:28]} — {bad}"})
                    write_live(live); continue
            except Exception: pass

        # Skip if unsubscribed (RGPD) — compté comme "ignoré". Supabase si dispo.
        if not test_email:
            try:
                unsub = supa.is_unsub(email) if supa.enabled() else db.is_unsubscribed(email)
                if unsub:
                    live["skipped"]=live.get("skipped",0)+1
                    live["log"].insert(0,{"ts":ts,"status":"info","msg":f"🚫 Désinscrit : {name[:35]}"})
                    write_live(live); continue
            except: pass

        # Skip if on suppression list (bounces / plaintes / blocage manuel)
        if not test_email and email.lower() in _suppressed:
            live["skipped"]=live.get("skipped",0)+1
            live["log"].insert(0,{"ts":ts,"status":"info","msg":f"🛡️ Supprimé (bounce/blocage) : {name[:30]}"})
            write_live(live); continue

        # Skip if already sent (not in test mode) — compté comme "ignoré"
        if not test_email and email.lower() in already_sent_emails():
            live["skipped"]=live.get("skipped",0)+1
            live["log"].insert(0,{"ts":ts,"status":"dim","msg":f"⏭️ Déjà envoyé : {name[:35]}"})
            write_live(live); continue

        # PDF (généré seulement si la campagne le demande)
        if cfg.get("attach_pdf", False):
            pdf,err=make_pdf(name,short)
            if not pdf:
                live["failed"]+=1
                live["log"].insert(0,{"ts":ts,"status":"err","msg":f"❌ PDF : {name[:30]} — {err}"})
                write_live(live); continue

        # Contact DB + tracking id
        track_id=None; contact_db_id=None
        if camp_id and not test_email:
            try:
                contact_db_id=db.ensure_contact(camp_id,name,email)
                track_id=contact_db_id
            except: pass

        # Send
        org={"short":short,"name":name,"emails":[email]}
        if track_id: org["track_id"]=track_id

        # Auto-template : choisit le bon modèle selon le type d'org
        tpl_tag=""
        if auto_tpl:
            otype=db.detect_org_type(name,email)
            tpl=db.template_for_orgtype(otype)
            if tpl:
                org["subject_override"]=tpl[0]
                org["body_override"]=tpl[1]
                tpl_tag=f" [{otype}]"

        ok_send,_,send_err=se.send_one(org,[email],attach_pdf=cfg.get("attach_pdf",False))

        if ok_send:
            live["sent"]+=1
            live["log"].insert(0,{"ts":ts,"status":"ok","msg":f"✅ {name[:33]}{tpl_tag} → {email}"})
            if not test_email:
                # #4a FIX : écriture atomique + lock (plus de corruption / pertes)
                append_log_entry(f"IFACE_{short}",
                    {"status":"sent","to":[email],"cc":se.CC_EMAILS,
                     "timestamp":time.strftime("%Y-%m-%d %H:%M:%S")})
                # Supabase : journal persistant cloud (dédup + quota survivent au redémarrage)
                if supa.enabled():
                    try: supa.log_sent(email, name, ",".join(se.CC_EMAILS))
                    except Exception: pass
                # DB : marque envoyé + planifie relance
                if contact_db_id:
                    try:
                        db.mark_sent(contact_db_id,email)
                        if followup_on:
                            db.schedule_followup(contact_db_id,followup_days)
                    except: pass
        else:
            live["failed"]+=1
            es=str(send_err)[:70] if send_err else "Erreur inconnue"
            live["log"].insert(0,{"ts":ts,"status":"err","msg":f"❌ {name[:30]}: {es}"})
            if send_err and "Disabled by user from hPanel" in str(send_err):
                live["log"].insert(0,{"ts":ts,"status":"err",
                    "msg":"⛔ Hostinger bloqué — arrêt. Réactivez via hPanel."})
                live["status"]="stopped"; write_live(live); return

        write_live(live)

        if i<len(targets)-1:
            live["log"].insert(0,{"ts":ts,"status":"dim","msg":f"⏸ Pause {delay}s..."})
            write_live(live)
            for s in range(delay):
                if read_ctrl()=="stop": live["status"]="stopped"; write_live(live); return
                while read_ctrl()=="pause":
                    live["status"]="paused"; live["eta"]=(len(targets)-i-1)*delay+(delay-s)
                    write_live(live); time.sleep(1)
                live["status"]="running"; live["eta"]=(len(targets)-i-1)*delay+(delay-s)
                write_live(live); time.sleep(1)

    live["status"]="done"; live["eta"]=0
    sk=live.get("skipped",0)
    live["log"].insert(0,{"ts":time.strftime("%H:%M:%S"),"status":"ok",
        "msg":f"🎉 Terminé — ✅ {live['sent']} envoyés / ❌ {live['failed']} échecs / ⏭️ {sk} ignorés"})
    write_live(live)

# ══ SESSION DEFAULTS ══════════════════════════════════════════
if "cfg" not in st.session_state:
    st.session_state["cfg"]={
        "subject":   "Exploring Participation Opportunities at LOGITERRE 2026.",
        "from_name": "LOGITERRE 2026 - Office of the Secretary General",
        "from_email":"a.zahraoui@logiterre-expo.com",
        "reply_to":  "sg@logiterre-expo.com",
        "cc":        "contact@uaotlafrica.com, sg@logiterre-expo.com",
        "delay":     120,
        "track_url": "",
        "followup_enabled": False,
        "followup_days": 7,
        "auto_template": False,
        "scheduled_ts": None,
        "validate_before_send": True,
        "plan_limit": 1000,
        "daily_guard": True,
        "attach_pdf": False,
        "body":"""Dear {name},

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
Tel / WhatsApp: +212 673 642 4246."""}

cfg=st.session_state["cfg"]
# Migration : garantit la présence des nouvelles clés
for _k,_v in [("track_url",""),("followup_enabled",False),("followup_days",7),
              ("auto_template",False),("scheduled_ts",None),("validate_before_send",True),
              ("plan_limit",100),("daily_guard",True),("attach_pdf",False),
              ("smtp_server","smtp.hostinger.com"),("smtp_port",465),("smtp_user",""),
              ("smtp_password",""),("smtp_from","")]:
    cfg.setdefault(_k,_v)
if "import_df" not in st.session_state: st.session_state["import_df"]=None
if "send_list" not in st.session_state: st.session_state["send_list"]=[]

# ══ SIDEBAR ═══════════════════════════════════════════════════
with st.sidebar:
    _side_logo = (f"<img src='{LOGO_URI}' style='width:82%;background:#fff;border-radius:10px;"
                  f"padding:8px;margin-bottom:.5rem;'>" if LOGO_URI
                  else "<div style='font-size:2.5rem;'>🌍</div>")
    st.markdown(f"""<div style="text-align:center;padding:1rem 0 .6rem;">
      {_side_logo}
      <div style="font-size:.75rem;opacity:.5;margin-top:.2rem;">Casablanca • 20–22 Oct 2026</div>
    </div>""",unsafe_allow_html=True)
    st.markdown("---")
    live=read_live(); status=live.get("status","idle")
    log=load_log()
    sent_c=total_sent()
    pdf_c=len(list(PDF_DIR.glob("*.pdf")))
    STATUS_ICONS={"running":"🟢","paused":"🟡","stopped":"🔴","done":"✅","idle":"⚪"}
    STATUS_LABELS={"running":"En cours","paused":"En pause","stopped":"Arrêté","done":"Terminé","idle":"Inactif"}
    st.markdown(f"""<div style="background:rgba(255,255,255,.07);border-radius:10px;padding:.8rem 1rem;margin-bottom:.5rem;">
      <div style="font-size:.65rem;opacity:.5;text-transform:uppercase;">Statut campagne</div>
      <div style="font-weight:700;font-size:.95rem;">{STATUS_ICONS.get(status,'⚪')} {STATUS_LABELS.get(status,'')}</div>
    </div>""",unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1: st.markdown(f"""<div style="background:rgba(255,255,255,.07);border-radius:10px;
      padding:.7rem;text-align:center;"><div style="font-size:.62rem;opacity:.5;text-transform:uppercase;">Emails</div>
      <div style="font-size:1.5rem;font-weight:800;">{sent_c}</div></div>""",unsafe_allow_html=True)
    with c2: st.markdown(f"""<div style="background:rgba(255,255,255,.07);border-radius:10px;
      padding:.7rem;text-align:center;"><div style="font-size:.62rem;opacity:.5;text-transform:uppercase;">PDFs</div>
      <div style="font-size:1.5rem;font-weight:800;">{pdf_c}</div></div>""",unsafe_allow_html=True)
    st.markdown("---")
    page=st.radio("Menu",[
        "🏠  Dashboard",
        "📊  Campagnes",
        "📤  Importer",
        "✍️  Composer",
        "📝  Templates",
        "🛡️  Validation",
        "📡  Délivrabilité",
        "🚀  Envoyer",
        "🔄  Relances",
        "👁️  Watch Live",
        "🎯  Engagement",
        "📨  Réponses IA",
        "✅  Inscriptions RSVP",
        "📈  Analytics & Rapport",
        "📬  Boîte mail IMAP",
        "🗄️  Bases de données",
        "⚙️  Paramètres",
    ],label_visibility="collapsed")
    st.markdown("---")
    # Utilisateur connecté + déconnexion
    _cur_user = st.session_state.get("auth_user")
    if _cur_user:
        st.markdown(f"""<div style="font-size:.78rem;opacity:.7;text-align:center;padding:.2rem;">
          👤 Connecté : <b>{_cur_user}</b></div>""",unsafe_allow_html=True)
        if st.button("🚪 Se déconnecter",use_container_width=True):
            st.session_state.pop("auth_user",None); st.rerun()
    st.markdown("""<div style="font-size:.68rem;opacity:.3;text-align:center;padding:.3rem;">
      sg@logiterre-expo.com<br>+212 673 642 4246</div>""",unsafe_allow_html=True)

# ════ 🏠 DASHBOARD ════════════════════════════════════════════
if "🏠" in page:
    page_header("Campagne · Casablanca 2026", "Tableau de bord",
                "Vue d'ensemble de la campagne d'invitations LOGITERRE 2026")

    # Données — Supabase (persistant cloud) si dispo, sinon SQLite/log local
    sa=total_sent()
    fa=sum(1 for v in log.values() if v.get("status")=="failed")
    rate=f"{sa*100//max(sa+fa,1)}%" if (sa+fa)>0 else "—"
    if supa.enabled():
        _rows, _S = engagement_data()
        n_open=_S["open"]; n_click=_S["click"]; n_rsvp=_S["reply"]
        n_yes=_S["yes"]; n_deleg=_S["deleg"]; n_unsub=_S["unsub"]
        if _S["sent"]>sa: sa=_S["sent"]
    else:
        opens=db.get_opens(); n_open=len(opens); n_click=0
        rstats=db.get_rsvp_stats(); n_rsvp=rstats.get("total",0) or 0; n_yes=rstats.get("yes",0) or 0
        n_deleg=rstats.get("total_delegates",0) or 0
        n_unsub=len(db.get_unsubscribes())

    # Liste unifiée des envois (Supabase si cloud, sinon log local)
    if supa.enabled():
        try:
            _sent_src=supa.get_sent()
            sent_events=[{"name":(r.get("org_name") or r.get("email","?")),
                          "email":r.get("email",""),"ts":(r.get("sent_at","") or "").replace("T"," ")}
                         for r in _sent_src if (r.get("status","sent")=="sent")]
        except Exception:
            sent_events=[]
    else:
        sent_events=[{"name":k.replace("PRUDENT_","").replace("UMF_","").replace("IFACE_","").replace("PRIORITY_",""),
                      "email":(v.get("to",[""])[0] if v.get("to") else ""),"ts":v.get("timestamp","")}
                     for k,v in log.items() if v.get("status")=="sent"]

    # Sparkline : 14 derniers jours d'activité
    from collections import Counter as _Ck
    dcount=_Ck(e["ts"][:10] for e in sent_events if e.get("ts"))
    days=sorted(dcount.items())[-14:]
    mx=max([n for _,n in days],default=1)
    spark="".join(f'<span style="height:{max(8,int(n/mx*42))}px"></span>' for _,n in days) or '<span></span>'

    # ── Hero band : grand chiffre + funnel ────────────────────
    def fr(label,val,total,color):
        pct=int(val/max(total,1)*100)
        return (f'<div class="funnel-row"><span class="fr-lbl">{label}</span>'
                f'<span class="fr-bar"><span class="fr-fill" style="width:{pct}%;background:{color};"></span></span>'
                f'<span class="fr-val">{val}</span></div>')
    funnel_html=(fr("Envoyés",sa,sa,"#6d5ee0")+fr("Ouverts",n_open,sa,"#3d9be0")
                 +fr("Cliqués",n_click,sa,"#d2691e")
                 +fr("Réponses",n_rsvp,sa,"#d2a017")+fr("Confirmés",n_yes,sa,"#0f8a4f"))
    H(f"""<div class="heroband">
    <div class="hb-left">
      <div class="hb-eyebrow">Emails envoyés</div>
      <div class="hb-num">{sa}</div>
      <div class="hb-cap">{rate} de réussite · {pdf_c} invitations PDF générées</div>
      <div class="hb-spark">{spark}</div>
    </div>
    <div class="hb-right">
      <div class="panel-title">Entonnoir d'engagement</div>
      {funnel_html}
    </div></div>""")

    # ── KPI tiles ─────────────────────────────────────────────
    c1,c2,c3,c4,c5=st.columns(5)
    with c1: kpi("Confirmés", n_yes, f"{n_deleg} délégués attendus", "#0f8a4f")
    with c2: kpi("Ouvertures", n_open, "suivi pixel", "#3d9be0")
    with c3: kpi("Clics", n_click, "ont cliqué le lien", "#d2691e")
    with c4: kpi("Échecs", fa, "à relancer", "#c8362f")
    with c5: kpi("Désinscrits", n_unsub, "RGPD", "#8a90a0")

    st.markdown("")
    ca,cb=st.columns([3,2])
    with ca:
        H('<div class="panel-title">Activité par jour</div>')
        if dcount:
            st.bar_chart(pd.DataFrame(sorted(dcount.items()),columns=["Date","Emails"]).set_index("Date"),
                         color="#3d2f8f",height=230)
        else:
            st.info("Pas encore d'envois enregistrés.")
    with cb:
        H('<div class="panel-title">Derniers envois</div>')
        recent=sorted(sent_events,key=lambda e:e.get("ts",""),reverse=True)[:7]
        if recent:
            rows="".join(
                f'<div class="feed-item"><div style="display:flex;align-items:center;overflow:hidden;">'
                f'<span class="fi-dot"></span><span class="fi-name">{(e["name"] or e["email"])[:30]}'
                f'</span></div><span class="fi-time">{e.get("ts","")[5:16]}</span></div>'
                for e in recent)
            H(f'<div class="panel">{rows}</div>')
        else:
            st.info("Aucun envoi.")

# ════ 📤 IMPORTER ═════════════════════════════════════════════
elif "📤" in page:
    page_header("Sources", "Importer des contacts", "Excel · CSV · Word · Texte brut — extraction intelligente")

    tab_file, tab_text, tab_saved = st.tabs(["📁 Fichier","✏️ Coller du texte","💾 Listes sauvegardées"])

    with tab_file:
        up=st.file_uploader("📂 Glisse ton fichier",type=["xlsx","xls","csv","docx"],
            help="Formats : Excel, CSV, Word")
        if up:
            sig=f"{up.name}:{up.size}"
            if st.session_state.get("_last_upload_sig")!=sig:
                st.session_state["_last_upload_sig"]=sig
                with st.spinner("🔍 Extraction..."):
                    fb=up.read(); ext=Path(up.name).suffix.lower()
                    try:
                        if ext in (".xlsx",".xls"): results=extract_from_xlsx(fb)
                        elif ext==".csv": results=extract_from_csv(fb)
                        else: results=extract_from_docx(fb)
                        st.session_state["import_df"]=pd.DataFrame(results)
                        srcname=Path(up.name).stem
                        st.session_state["import_src_name"]=srcname
                        # 💾 Sauvegarde AUTOMATIQUE persistante, sous le nom du fichier
                        saved_ok=False
                        try: saved_ok=list_store_save(srcname, results)
                        except Exception: saved_ok=False
                        where="☁️ cloud" if supa.enabled() else "local"
                        if saved_ok:
                            st.success(f"✅ {len(results)} organisation(s) extraite(s) depuis **{up.name}** — "
                                       f"💾 sauvegardé sous «{srcname}» ({where}), géré dans 🗄️ Bases de données")
                        else:
                            st.success(f"✅ {len(results)} organisation(s) extraite(s) depuis **{up.name}**")
                    except Exception as e:
                        st.error(f"❌ Erreur extraction : {e}")

    with tab_text:
        st.markdown("Colle des emails ou une liste (1 par ligne, ou format `Nom — email`) :")
        txt=st.text_area("",height=180,placeholder="Harvard Business School — research@hbs.edu\ninfo@fiata.org\nMIT CTL — ctl@mit.edu",
                         label_visibility="collapsed")
        if st.button("🔍 Extraire",use_container_width=True,type="primary") and txt.strip():
            results=extract_from_text(txt)
            if results:
                st.session_state["import_df"]=pd.DataFrame(results)
                st.success(f"✅ {len(results)} organisation(s) trouvée(s)")
            else:
                st.warning("Aucun email valide trouvé.")

    with tab_saved:
        saved=list_store_load()
        if saved:
            if supa.enabled(): st.caption("☁️ Listes persistantes (Supabase) — conservées même après redéploiement.")
            for i,d in enumerate(saved):
                dname=d["name"]; drows=d["rows"]; dsaved=d.get("saved","")
                k=safe_fn(dname) or f"l{i}"
                c_n,c_l,c_d=st.columns([3,1,1])
                with c_n: st.markdown(f"**{dname}** — {len(drows)} contacts — *{dsaved}*")
                with c_l:
                    if st.button("📂 Charger",key=f"load_{k}_{i}",use_container_width=True):
                        st.session_state["import_df"]=pd.DataFrame(drows)
                        st.success(f"✅ Liste «{dname}» chargée")
                with c_d:
                    if st.button("🗑️ Suppr.",key=f"del_{k}_{i}",use_container_width=True):
                        list_store_delete(dname); st.rerun()
        else:
            st.info("Aucune liste sauvegardée. Importe un fichier — il sera sauvegardé automatiquement sous son nom.")

    # ── Affichage et édition ──────────────────────────────────
    if st.session_state["import_df"] is not None and not st.session_state["import_df"].empty:
        df=st.session_state["import_df"]
        if "✅ Sélect." not in df.columns: df.insert(0,"✅ Sélect.",True)

        st.markdown("---")
        r1,r2,r3=st.columns([4,1,1])
        with r1:
            st.markdown(f'<div class="section-title">📋 {len(df)} organisation(s) — éditable</div>',
                        unsafe_allow_html=True)
        with r2:
            if st.button("☑️ Tout",use_container_width=True):
                df["✅ Sélect."]=True; st.session_state["import_df"]=df; st.rerun()
        with r3:
            if st.button("☐ Aucun",use_container_width=True):
                df["✅ Sélect."]=False; st.session_state["import_df"]=df; st.rerun()

        # Stats rapides
        new_c=sum(1 for _,r in df.iterrows() if r.get("statut","")=="🆕 Nouveau")
        sent_c2=sum(1 for _,r in df.iterrows() if r.get("statut","")=="✅ Déjà envoyé")
        c1,c2,c3=st.columns(3)
        c1.metric("🆕 Nouveaux",new_c)
        c2.metric("✅ Déjà envoyés",sent_c2)
        c3.metric("📋 Total",len(df))

        col_cfg={"✅ Sélect.":st.column_config.CheckboxColumn("✅",width="small"),
                 "name":st.column_config.TextColumn("🏛️ Organisation",width="large"),
                 "email":st.column_config.TextColumn("📧 Email à envoyer",width="medium"),
                 "tous_emails":st.column_config.TextColumn("📋 Tous les emails",width="large",disabled=True),
                 "statut":st.column_config.TextColumn("Statut",width="small",disabled=True)}
        if "tous_emails" not in df.columns: del col_cfg["tous_emails"]
        if "statut" not in df.columns: del col_cfg["statut"]

        edited=st.data_editor(df,key="import_editor",column_config=col_cfg,
                               use_container_width=True,num_rows="dynamic",
                               height=min(80+len(df)*38,500))
        st.session_state["import_df"]=edited

        selected=edited[edited["✅ Sélect."]==True]
        if not selected.empty:
            st.success(f"✅ **{len(selected)}** sélectionnée(s)")
            r_a,r_b,r_c=st.columns(3)
            with r_a:
                if st.button("🚀 Envoyer les sélectionnées",type="primary",use_container_width=True):
                    st.session_state["send_list"]=selected[["name","email"]].to_dict("records")
                    st.rerun()
            with r_b:
                list_name=st.text_input("Nom de la liste",
                                        value=st.session_state.get("import_src_name",""),
                                        placeholder="ex: Fédérations Europe",
                                        label_visibility="collapsed")
            with r_c:
                if st.button("💾 Sauvegarder la liste",use_container_width=True) and list_name:
                    list_store_save(list_name,edited.to_dict("records"))
                    where="☁️ cloud" if supa.enabled() else "local"
                    st.success(f"✅ Liste «{list_name}» sauvegardée ({where}) !")
        else:
            st.warning("☝️ Coche au moins une organisation.")

# ════ ✍️ COMPOSER ═════════════════════════════════════════════
elif "✍️" in page:
    page_header("Message", "Composer l'email", "Personnalise chaque aspect de l'invitation")
    c1,c2=st.columns(2)
    with c1:
        st.markdown('<div class="section-title">📌 En-têtes</div>',unsafe_allow_html=True)
        cfg["subject"]  =st.text_input("📌 Objet (Subject)",value=cfg["subject"])
        cfg["from_name"]=st.text_input("👤 Nom expéditeur",value=cfg["from_name"])
        cfg["from_email"]=st.text_input("📮 Email expéditeur",value=cfg["from_email"])
        cfg["reply_to"] =st.text_input("↩️ Reply-To",value=cfg["reply_to"])
        cfg["cc"]       =st.text_input("📋 CC",value=cfg["cc"])
        cfg["delay"]    =st.slider("⏱️ Délai entre emails (sec)",30,300,cfg["delay"],10,
                                    help="120s recommandé — anti-spam Hostinger")
        cfg["validate_before_send"]=st.toggle("🛡️ Valider chaque email avant envoi",
            value=cfg.get("validate_before_send",True),
            help="Vérifie format + domaine MX + Spamhaus avant chaque envoi (skip les invalides)")
        cfg["attach_pdf"]=st.toggle("📎 Joindre l'invitation PDF",
            value=cfg.get("attach_pdf",False),
            help="Désactivé = email seul (plus léger, meilleure délivrabilité). Activé = génère + joint le PDF d'invitation.")
        st.caption("📎 PDF joint" if cfg["attach_pdf"] else "✉️ Email sans pièce jointe")
        st.info(f"📊 Pour 10 emails : ~{10*cfg['delay']//60}min | Pour 50 : ~{50*cfg['delay']//60}min")
    with c2:
        st.markdown('<div class="section-title">📝 Corps du message</div>',unsafe_allow_html=True)
        cfg["body"]=st.text_area("",value=cfg["body"],height=360,label_visibility="collapsed")
        st.caption("💡 Variables auto : **{name}** (nom/orga · évite le spam « Dear Sir/Madam »), "
                   "**{first_name}**, **{org}**, **{email}** — remplacées pour chaque destinataire.")

    st.markdown("---")
    # ── Tracking + Relances ───────────────────────────────────
    t1,t2=st.columns(2)
    with t1:
        st.markdown('<div class="section-title">📡 Suivi d\'ouverture (tracking)</div>',unsafe_allow_html=True)
        cfg["track_url"]=st.text_input("URL du serveur de tracking",value=cfg.get("track_url",""),
            placeholder="http://localhost:8765 ou https://xxx.ngrok.io",
            help="Lance tracking_server.py puis colle l'URL. Vide = pas de tracking.")
        if cfg["track_url"]:
            st.success("📡 Tracking activé — pixel + lien désinscription injectés")
        else:
            st.caption("💡 Active le suivi pour savoir QUI ouvre tes emails")
    with t2:
        st.markdown('<div class="section-title">🔄 Relances automatiques</div>',unsafe_allow_html=True)
        cfg["followup_enabled"]=st.toggle("Activer les relances",value=cfg.get("followup_enabled",False),
            help="Programme une relance pour ceux qui ne répondent pas")
        cfg["followup_days"]=st.slider("Relance après (jours)",2,30,cfg.get("followup_days",7),1,
            disabled=not cfg["followup_enabled"])
        if cfg["followup_enabled"]:
            st.success(f"🔄 Relance programmée à J+{cfg['followup_days']} pour les non-répondants")

    st.markdown("---")
    a1,a2=st.columns(2)
    with a1:
        st.markdown('<div class="section-title">🤖 Auto-template intelligent</div>',unsafe_allow_html=True)
        cfg["auto_template"]=st.toggle("Adapter le template par type d'organisation",
            value=cfg.get("auto_template",False),
            help="Chaque destinataire reçoit le modèle adapté à son type")
        if cfg["auto_template"]:
            st.success("🤖 Université→Académique · Ministère→Gouvernement · Port→Industrie · etc.")
            st.caption("Les contacts 'général' gardent le corps ci-dessus.")
        else:
            st.caption("💡 Active pour personnaliser automatiquement chaque email")
    with a2:
        st.markdown('<div class="section-title">⏰ Envoi programmé</div>',unsafe_allow_html=True)
        sched_on=st.toggle("Programmer l'envoi à une date/heure",
            value=cfg.get("scheduled_ts") is not None)
        if sched_on:
            import datetime as _dt
            d1,d2=st.columns(2)
            with d1: sd=st.date_input("Date",value=_dt.date.today())
            with d2: stime=st.time_input("Heure",value=_dt.time(9,0))
            sched_dt=_dt.datetime.combine(sd,stime)
            cfg["scheduled_ts"]=sched_dt.timestamp()
            st.success(f"⏰ Envoi le {sched_dt.strftime('%d/%m/%Y à %H:%M')}")
        else:
            cfg["scheduled_ts"]=None
            st.caption("💡 Programme l'envoi pour l'heure optimale (ex: 9h)")

    st.markdown("---")
    st.markdown('<div class="section-title">👁️ Prévisualisation</div>',unsafe_allow_html=True)
    st.markdown(f"""<div style="background:#0d1117;border-radius:12px;padding:1.3rem;
      font-family:'Courier New',monospace;font-size:.8rem;color:#58a6ff;
      border:1px solid #21262d;white-space:pre-wrap;line-height:1.6;max-height:300px;overflow-y:auto;">
<span style="color:#d29922;">De     :</span> {cfg['from_name']} &lt;{cfg['from_email']}&gt;
<span style="color:#d29922;">À      :</span> [destinataire@organisation.com]
<span style="color:#d29922;">CC     :</span> {cfg['cc']}
<span style="color:#d29922;">Objet  :</span> <span style="color:#3fb950;">{cfg['subject'][:90]}</span>
<span style="color:#d29922;">PDF    :</span> LOGITERRE_2026_Invitation_[Org].pdf
<span style="color:#484f58;">━━━━━━━━━━━━━━━━━━━━━━━━━</span>
<span style="color:#e6edf3;">{cfg['body'][:350].replace('<','&lt;').replace('>','&gt;')}...</span>
    </div>""",unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        if st.button("💾 Sauvegarder",type="primary",use_container_width=True):
            st.session_state["cfg"]=cfg; st.success("✅ Sauvegardé !")
    with c2:
        if st.button("🔄 Réinitialiser le corps",use_container_width=True):
            st.session_state["cfg"]["body"]=st.session_state["cfg"]["body"]; st.rerun()

# ════ 🛡️ VALIDATION ══════════════════════════════════════════
elif "🛡️" in page:
    page_header("Délivrabilité", "Validation des emails", "Format · Domaine MX · Jetable · Spamhaus · Blacklist expéditeur")

    try:
        import email_validator as ev
    except Exception as e:
        st.error(f"❌ Module de validation indisponible : {e}"); st.stop()

    st.markdown('<div class="section-title">📡 Réputation de l\'expéditeur</div>',unsafe_allow_html=True)
    if st.button("🔍 Vérifier si NOTRE serveur est blacklisté (Spamhaus ZEN)",use_container_width=True):
        with st.spinner("Vérification Spamhaus ZEN..."):
            bl=ev.check_sender_blacklist()
        smtp=bl.get("smtp",{})
        if smtp.get("listed") is True:
            st.error(f"🔴 ALERTE : serveur d'envoi BLACKLISTÉ — {smtp.get('info')}")
            st.markdown("**Action :** contacte Hostinger. Tes emails iront en spam.")
        elif smtp.get("listed") is False:
            st.success(f"✅ Serveur d'envoi PROPRE — {smtp.get('info')}")
        else:
            st.warning(f"⏱️ {smtp.get('info')}")
        if "local" in bl:
            st.caption(f"IP locale : {bl['local']['info']}")

    # ── SPF / DKIM / DMARC ────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">🔐 Authentification du domaine (SPF · DKIM · DMARC)</div>',
                unsafe_allow_html=True)
    st.caption("Le facteur #1 de délivrabilité. Sans ces enregistrements, tes emails finissent en spam.")
    dom_check=st.text_input("Domaine à vérifier",value="logiterre-expo.com")
    if st.button("🔐 Vérifier SPF / DKIM / DMARC",use_container_width=True):
        try:
            import dns_checker as dc
            with st.spinner(f"Analyse DNS de {dom_check}..."):
                res=dc.full_check(dom_check)
            score=res["score"]; verdict=res["verdict"]
            vcolor={"excellent":"#238636","correct":"#1f6feb","faible":"#d29922","critique":"#da3633"}[verdict]
            st.markdown(f"""<div style="background:{vcolor}15;border:2px solid {vcolor};border-radius:12px;
              padding:1rem 1.4rem;margin:.5rem 0;">
              <span style="font-size:1.6rem;font-weight:800;color:{vcolor};">{score}/100</span>
              <span style="font-size:1.1rem;color:{vcolor};margin-left:.5rem;text-transform:uppercase;">{verdict}</span>
            </div>""",unsafe_allow_html=True)
            for key,icon in [("spf","SPF"),("dkim","DKIM"),("dmarc","DMARC")]:
                r=res[key]; ok=r["status"]=="ok"
                clr="#238636" if ok else ("#d29922" if r["status"]=="unknown" else "#da3633")
                ico="✅" if ok else ("⏱️" if r["status"]=="unknown" else "❌")
                st.markdown(f"<div style='padding:.4rem 0;'><b style='color:{clr};'>{ico} {icon}</b> — {r['msg']}</div>",
                            unsafe_allow_html=True)
                if r.get("record"):
                    st.caption(f"`{r['record'][:90]}`")
            if score<100:
                st.info("💡 **Pour améliorer :** ajoute les enregistrements manquants dans le DNS de ton domaine "
                        "(via hPanel Hostinger → DNS). DMARC `p=quarantine` ou `p=reject` recommandé.")
        except Exception as e:
            st.error(f"❌ {e}")

    st.markdown("---")
    st.markdown('<div class="section-title">📋 Valider une liste d\'emails</div>',unsafe_allow_html=True)

    source_rows=[r for r in st.session_state.get("send_list",[]) if r.get("email")]
    st.caption(f"Source : **liste d'envoi** ({len(source_rows)} contacts). Ou colle des emails ci-dessous.")
    c1,c2,c3=st.columns(3)
    with c1:
        deep=st.toggle("Format + MX",value=True,help="Syntaxe + domaine qui peut recevoir")
    with c2:
        do_spam=st.toggle("Spamhaus",value=True,help="Domaine sur liste noire")
    with c3:
        do_smtp=st.toggle("Existence boîte (SMTP)",value=False,
                          help="Interroge le serveur : la boîte existe-t-elle vraiment ? pleine ? "
                               "⚠️ plus lent + souvent bloqué par les FAI (port 25)")
    if do_smtp:
        st.markdown('<div class="alert-box">⚠️ La vérification SMTP interroge directement le serveur '
                    'du destinataire (existence réelle, boîte pleine). Elle est plus lente (~5-10s/email) '
                    'et peut être bloquée si ton FAI filtre le port 25.</div>',unsafe_allow_html=True)

    pasted=st.text_area("Emails à valider (1 par ligne) — optionnel",height=100,
        placeholder="research@hbs.edu\ninfo@fiata.org")

    emails_to_check=[]
    if pasted.strip():
        emails_to_check=[l.strip() for l in pasted.splitlines() if "@" in l]
    elif source_rows:
        emails_to_check=[r["email"] for r in source_rows]

    if st.button(f"🛡️ Valider {len(emails_to_check)} email(s)",type="primary",
                 use_container_width=True,disabled=not emails_to_check):
        prog=st.progress(0,text="Validation...")
        results=[]
        for i,em in enumerate(emails_to_check):
            results.append(ev.validate_email_full(em,check_dns=deep,check_spamhaus=do_spam,check_smtp=do_smtp))
            prog.progress((i+1)/len(emails_to_check),text=f"[{i+1}/{len(emails_to_check)}] {em}")
        prog.empty()
        st.session_state["validation_results"]=results

    if st.session_state.get("validation_results"):
        results=st.session_state["validation_results"]
        ok_n=sum(1 for r in results if r["level"]=="ok")
        err_n=sum(1 for r in results if r["level"]=="error")
        c1,c2,c3=st.columns(3)
        c1.metric("✅ Valides",ok_n)
        c2.metric("❌ À exclure",err_n)
        c3.metric("📋 Total",len(results))
        df_v=pd.DataFrame([{
            "Statut":{"ok":"✅","error":"❌"}.get(r["level"],"⚠️"),
            "Email":r["email"],"Diagnostic":r["status"],
            "Détails":" ".join(r["badges"]),"Raison":r["reason"],
        } for r in results])
        st.dataframe(df_v,use_container_width=True,hide_index=True,height=320)
        if err_n>0:
            st.warning(f"⚠️ {err_n} email(s) problématique(s)")
            if st.button("🧹 Garder uniquement les valides dans la liste d'envoi",
                         type="primary",use_container_width=True):
                valid_emails={r["email"] for r in results if r["level"]=="ok"}
                kept=[r for r in st.session_state.get("send_list",[]) if r.get("email") in valid_emails]
                if not kept:
                    kept=[{"name":e.split("@")[1].split(".")[0].title(),"email":e} for e in valid_emails]
                st.session_state["send_list"]=kept
                st.success(f"✅ Liste nettoyée : {len(valid_emails)} valides → va dans 🚀 Envoyer")
        else:
            st.success("🎉 Tous les emails sont valides et délivrables !")

# ════ 🚀 ENVOYER ══════════════════════════════════════════════
elif "🚀" in page:
    page_header("Diffusion", "Lancer l'envoi", "▶️ Démarrer &nbsp;·&nbsp; ⏸️ Pause &nbsp;·&nbsp; ⏹️ Stop")
    live=read_live(); status=live.get("status","idle")
    is_active=status in ("running","paused","scheduled")
    sent=live.get("sent",0); failed=live.get("failed",0); skipped=live.get("skipped",0)
    total=live.get("total",0); done_n=sent+failed+skipped
    pct=min(done_n/max(total,1),1.0)

    if not is_active:
        st.markdown('<div class="section-title">📋 Liste des destinataires</div>',unsafe_allow_html=True)
        sl=st.session_state.get("send_list",[])
        if not sl: sl=[{"name":"","email":""}]
        df2=pd.DataFrame(sl)
        edited2=st.data_editor(df2,key="send_editor",
            column_config={"name":st.column_config.TextColumn("🏛️ Organisation",width="large"),
                           "email":st.column_config.TextColumn("📧 Email",width="medium")},
            use_container_width=True,num_rows="dynamic",height=280)
        st.session_state["send_list"]=edited2.to_dict("records")
        valid=edited2[edited2["email"].str.contains("@",na=False)&(edited2["name"].str.len()>0)]
        invalid_emails=[r["email"] for _,r in valid.iterrows() if not validate_email(r["email"])]
        if invalid_emails:
            st.markdown(f'<div class="alert-box">⚠️ Emails invalides détectés : {", ".join(invalid_emails[:5])}</div>',
                        unsafe_allow_html=True)
        c1,c2,c3=st.columns(3)
        c1.metric("✅ Valides",len(valid)-len(invalid_emails))
        c2.metric("⚠️ Invalides",len(invalid_emails))
        c3.metric("⏱️ Durée estimée",f"~{len(valid)*cfg['delay']//60}min")

        # Test send — synchrone, feedback fiable
        st.markdown("---")
        st.markdown('<div class="section-title">🧪 Test avant envoi</div>',unsafe_allow_html=True)
        test_em=st.text_input("📧 Envoyer un test à",value=cfg["from_email"],
                               help="Envoie 1 email de test à cette adresse (avec le PDF + tracking)")
        if st.button("📤 Envoyer le test",use_container_width=True,type="primary"):
            if not validate_email(test_em):
                st.error("❌ Email de test invalide")
            else:
                # nom d'org : 1ère ligne valide, sinon générique
                test_name = "LOGITERRE — Test"
                if not valid.empty:
                    test_name = str(valid.iloc[0].get("name") or "LOGITERRE — Test")
                with st.spinner(f"Génération PDF + envoi vers {test_em}…"):
                    try:
                        import send_emails as se
                        se.SUBJECT   = cfg["subject"]
                        se.BODY      = cfg.get("body", se.BODY)
                        se.FROM_NAME = cfg["from_name"]; se.FROM_EMAIL = cfg["from_email"]
                        se.REPLY_TO  = cfg["reply_to"]
                        # SMTP configurable (même réglage que l'envoi réel)
                        if cfg.get("smtp_server"):   se.SMTP_SERVER = cfg["smtp_server"].strip()
                        if cfg.get("smtp_port"):
                            try: se.SMTP_PORT = int(cfg["smtp_port"])
                            except Exception: pass
                        if cfg.get("smtp_user"):     se.SMTP_USER = se.FROM_EMAIL = cfg["smtp_user"].strip()
                        if cfg.get("smtp_from"):     se.FROM_EMAIL = cfg["smtp_from"].strip()
                        if cfg.get("smtp_password"): se.SMTP_PASSWORD = cfg["smtp_password"]
                        se.CC_EMAILS = []   # pas de CC sur un test
                        se.TRACK_BASE_URL = cfg.get("track_url","").rstrip("/")
                        se.ATTACH_PDF = bool(cfg.get("attach_pdf", False))
                        if not se.SMTP_PASSWORD:
                            st.error("❌ Aucun mot de passe SMTP configuré (.streamlit/secrets.toml ou Secrets)")
                            st.stop()
                        short = safe_fn(test_name) or "test"
                        want_pdf = bool(cfg.get("attach_pdf", False))
                        pdf, perr = (make_pdf(test_name, short) if want_pdf else (True, None))
                        if want_pdf and not pdf:
                            st.error(f"❌ Échec génération PDF : {perr}")
                        else:
                            org = {"short":short,"name":test_name,"emails":[test_em]}
                            # tracking si activé
                            if cfg.get("track_url"):
                                try:
                                    cid_t = db.get_default_campaign()
                                    org["track_id"] = db.ensure_contact(cid_t, test_name, test_em)
                                except: pass
                            ok, _, serr = se.send_one(org, [test_em], test_mode=True,
                                                      attach_pdf=cfg.get("attach_pdf",False))
                            if ok:
                                st.success(f"✅ Test envoyé à {test_em} ! Vérifie ta boîte (et les Promotions/Spam).")
                                st.balloons()
                            else:
                                msg = f"{type(serr).__name__}: {serr}" if serr else "erreur inconnue"
                                st.error(f"❌ Échec envoi : {msg}")
                                if serr and "Disabled by user from hPanel" in str(serr):
                                    st.warning("⛔ Compte Hostinger bloqué — réactive-le dans hPanel → Emails.")
                    except Exception as e:
                        st.error(f"❌ Erreur : {type(e).__name__}: {e}")

    st.markdown("---")
    # Status + Progress
    pill={"running":"<span class='pill-run'>🟢 En cours</span>",
          "paused":"<span class='pill-pause'>🟡 En pause</span>",
          "stopped":"<span class='pill-stop'>🔴 Arrêté</span>",
          "done":"<span class='pill-done'>✅ Terminé</span>",
          "scheduled":"<span class='pill-pause'>⏰ Programmé</span>",
          "idle":"<span class='pill-idle'>⚪ Inactif</span>"}
    st.markdown(f"**Statut :** {pill.get(status,pill['idle'])}",unsafe_allow_html=True)
    if total>0:
        eta=live.get("eta",0)
        st.markdown(f"""<div class="prog-wrap"><div class="prog-fill" style="width:{pct*100:.1f}%"></div></div>
          <div style="display:flex;justify-content:space-between;font-size:.82rem;color:#555;margin:.3rem 0;">
            <span>✅ {sent} envoyés · ❌ {failed} échecs · ⏭️ {skipped} ignorés · 📋 {max(total-done_n,0)} restants</span>
            <span>⏱️ ETA {eta//60}m {eta%60:02d}s</span></div>
          <div style="font-size:.8rem;color:#888;">📤 {live.get('current','')}</div>""",
          unsafe_allow_html=True)
        st.markdown("")

    c_play,c_pause,c_stop=st.columns(3)
    with c_play:
        if st.button("▶️ Démarrer / Reprendre",use_container_width=True,type="primary",
                     disabled=status in ("running","scheduled")):
            if status in ("idle","done","stopped"):
                valid_t=pd.DataFrame(st.session_state.get("send_list",[]))
                valid_t=valid_t[valid_t["email"].str.contains("@",na=False)&(valid_t["name"].str.len()>0)] if not valid_t.empty else valid_t
                if valid_t.empty: st.error("❌ Liste vide !"); st.stop()
                # #1 FIX : campaign_id résolu ici (thread principal) et passé via cfg
                launch_cfg=dict(cfg); launch_cfg["campaign_id"]=st.session_state.get("active_campaign")
                # #2 FIX : écrit "running" AVANT le spawn → ferme la fenêtre de double-lancement
                write_live({"status":"running","total":len(valid_t),"sent":0,"failed":0,
                            "skipped":0,"current":"Initialisation...","eta":len(valid_t)*cfg["delay"],"log":[]})
                write_ctrl("run")
                t=threading.Thread(target=send_background,
                    args=(valid_t.to_dict("records"),launch_cfg),daemon=True)
                t.start(); st.rerun()
            else:
                write_ctrl("run"); st.rerun()
    with c_pause:
        if st.button("⏸️ Pause",use_container_width=True,disabled=status!="running"):
            write_ctrl("pause"); st.rerun()
    with c_stop:
        if st.button("⏹️ Stop",use_container_width=True,disabled=status not in ("running","paused")):
            write_ctrl("stop"); st.rerun()

    if live.get("log"):
        st.markdown("")
        log_html="".join(f'<div class="{e.get("status","dim")}">[{e["ts"]}] {e["msg"]}</div>'
                         for e in live["log"][:15])
        st.markdown(f'<div class="console">{log_html}</div>',unsafe_allow_html=True)
    if is_active: time.sleep(2); st.rerun()

# ════ 👁️ WATCH LIVE ═══════════════════════════════════════════
elif "👁️" in page:
    page_header("Monitoring temps réel", "Watch Live", "Monitoring temps réel · Auto-refresh toutes les 2s")
    live=read_live(); status=live.get("status","idle")
    total=live.get("total",0); sent=live.get("sent",0); failed=live.get("failed",0)
    skipped=live.get("skipped",0)
    done_n=sent+failed+skipped; pct=min(int(done_n/max(total,1)*100),100)
    c1,c2,c3,c4=st.columns(4)
    for col,(val,lbl,col_) in zip([c1,c2,c3,c4],[
        (f"{pct}%","Progression","#302b63"),(sent,"Envoyés","#238636"),
        (failed,"Échecs","#da3633"),(f"{live.get('eta',0)//60}m {live.get('eta',0)%60:02d}s","ETA","#8957e5")]):
        with col: st.markdown(f"""<div class="kpi" style="border-top-color:{col_};">
          <div class="k-label">{lbl}</div>
          <div class="k-val" style="color:{col_};">{val}</div></div>""",unsafe_allow_html=True)
    if total>0:
        st.markdown(f"""<div class="prog-wrap" style="height:14px;margin:.8rem 0;">
          <div class="prog-fill" style="width:{pct}%"></div></div>
          <div style="text-align:center;font-size:.8rem;color:#888;">{done_n}/{total} · {live.get('current','')}</div>""",
          unsafe_allow_html=True)
    st.markdown("")
    pill={"running":"<span class='pill-run'>🟢 RUNNING</span>",
          "paused":"<span class='pill-pause'>🟡 PAUSED</span>",
          "stopped":"<span class='pill-stop'>🔴 STOPPED</span>",
          "scheduled":"<span class='pill-pause'>⏰ SCHEDULED</span>",
          "done":"<span class='pill-done'>✅ DONE</span>","idle":"<span class='pill-idle'>⚪ IDLE</span>"}
    logs=live.get("log",[])
    log_html="".join(f'<div class="{e.get("status","dim")}">[{e.get("ts","--")}] {e.get("msg","")}</div>'
                     for e in logs[:60]) or '<div class="dim">En attente de l\'envoi...</div>'
    st.markdown(f"""<div class="console" style="min-height:360px;">
      <div style="margin-bottom:8px;border-bottom:1px solid #21262d;padding-bottom:6px;">
        {pill.get(status,pill['idle'])} &nbsp;
        <span style="color:#484f58;font-size:.72rem;">Auto-refresh actif</span></div>
      {log_html}</div>""",unsafe_allow_html=True)
    ca,cb,cc=st.columns(3)
    with ca:
        if st.button("▶️ Reprendre",use_container_width=True,disabled=status!="paused"):
            write_ctrl("run"); st.rerun()
    with cb:
        if st.button("⏸️ Pause",use_container_width=True,disabled=status!="running"):
            write_ctrl("pause"); st.rerun()
    with cc:
        if st.button("⏹️ Stop",use_container_width=True,disabled=status not in ("running","paused")):
            write_ctrl("stop"); st.rerun()
    st.markdown("---")
    st.markdown('<div class="section-title">📊 Historique — 100 derniers envois</div>',unsafe_allow_html=True)
    log=load_log()
    all_sent=sorted([(k,v) for k,v in log.items() if v.get("status")=="sent"],
                    key=lambda x:x[1].get("timestamp",""),reverse=True)[:100]
    if all_sent:
        st.dataframe(pd.DataFrame([{"Date":v.get("timestamp","")[:16],
            "Organisation":k.replace("PRUDENT_","").replace("UMF_","").replace("IFACE_","").replace("PRIORITY_","")[:40],
            "Email":v.get("to",["?"])[0]} for k,v in all_sent]),
            use_container_width=True,hide_index=True,height=280)
    if status in ("running","paused","scheduled"): time.sleep(2); st.rerun()

# ════ 🗄️ BASES DE DONNÉES ═════════════════════════════════════
elif "🗄️" in page:
    page_header("Données", "Bases de données",
                "Gère tes bases de contacts : renommer · fusionner · dédupliquer · exporter")
    saved=list_store_load()
    st.caption("☁️ Stockées dans Supabase — persistent même après redéploiement du cloud."
               if supa.enabled() else
               "💾 Stockées en local — configure Supabase (Secrets) pour la persistance cloud.")

    # ── Vue d'ensemble ────────────────────────────────────────
    all_emails=[(r.get("email","") or "").lower().strip()
                for d in saved for r in d["rows"] if (r.get("email","") or "").strip()]
    k1,k2,k3=st.columns(3)
    k1.metric("🗄️ Bases", len(saved))
    k2.metric("👥 Contacts (total)", len(all_emails))
    k3.metric("✉️ Emails uniques", len(set(all_emails)))

    if not saved:
        st.info("💡 Aucune base. Importe un fichier dans 📤 Importer — il est sauvegardé automatiquement sous son nom.")
    else:
        # ── Tableau récapitulatif ─────────────────────────────
        st.markdown('<div class="section-title">📊 Tes bases</div>',unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{
            "🗄️ Nom": d["name"],
            "👥 Contacts": len(d["rows"]),
            "✉️ Uniques": len({(r.get("email","") or "").lower().strip() for r in d["rows"] if r.get("email")}),
            "📅 Sauvegardé": d.get("saved",""),
        } for d in saved]),use_container_width=True,hide_index=True)

        # ── Gérer chaque base ─────────────────────────────────
        st.markdown('<div class="section-title">⚙️ Gérer une base</div>',unsafe_allow_html=True)
        for i,d in enumerate(saved):
            rows=d["rows"]; dname=d["name"]; dsaved=d.get("saved","")
            k=safe_fn(dname) or f"l{i}"
            with st.expander(f"🗄️ **{dname}** — {len(rows)} contacts — *{dsaved}*"):
                df_s=pd.DataFrame(rows)
                if not df_s.empty:
                    cols=["name","email"] if "name" in df_s.columns else df_s.columns.tolist()
                    st.dataframe(df_s[cols[:3]],use_container_width=True,hide_index=True,height=180)
                # ✏️ Renommer
                rn1,rn2=st.columns([3,1])
                with rn1:
                    newname=st.text_input("Nouveau nom",value=dname,key=f"rn_{k}_{i}",
                                          label_visibility="collapsed")
                with rn2:
                    if st.button("✏️ Renommer",key=f"rnb_{k}_{i}",use_container_width=True):
                        ok,msg=list_store_rename(dname,newname)
                        (st.success if ok else st.error)(msg)
                        if ok: st.rerun()
                # Actions
                a1,a2,a3=st.columns(3)
                with a1:
                    if st.button("📂 Charger & Envoyer",key=f"ls_{k}_{i}",type="primary",use_container_width=True):
                        st.session_state["send_list"]=[{"name":r.get("name",""),"email":r.get("email","")} for r in rows]
                        st.success(f"✅ {len(rows)} contacts chargés → 🚀 Envoyer")
                with a2:
                    buf=io.BytesIO()
                    pd.DataFrame(rows)[["name","email"] if "name" in pd.DataFrame(rows).columns else ["email"]]\
                      .to_csv(buf,index=False); buf.seek(0)
                    st.download_button("⬇️ CSV",data=buf,file_name=f"{k}.csv",
                                       mime="text/csv",use_container_width=True,key=f"dl_{k}_{i}")
                with a3:
                    if st.button("🗑️ Supprimer",key=f"ds_{k}_{i}",use_container_width=True):
                        list_store_delete(dname); st.rerun()

        # ── Outils : fusionner / dédupliquer ──────────────────
        st.markdown("---")
        st.markdown('<div class="section-title">🛠️ Outils</div>',unsafe_allow_html=True)
        names=[d["name"] for d in saved]
        tA,tB=st.columns(2)
        with tA:
            st.markdown("**🔗 Fusionner** (déduplique par email)")
            picks=st.multiselect("Bases à fusionner",names,key="merge_pick",label_visibility="collapsed")
            mergename=st.text_input("Nom de la base fusionnée",key="merge_name",
                                    placeholder="ex: Toutes_Europe")
            if st.button("🔗 Fusionner",use_container_width=True):
                if len(picks)<2: st.warning("Choisis au moins 2 bases.")
                elif not mergename.strip(): st.warning("Donne un nom à la base fusionnée.")
                else:
                    byemail={}
                    for d in saved:
                        if d["name"] in picks:
                            for r in d["rows"]:
                                e=(r.get("email","") or "").lower().strip()
                                if e and e not in byemail: byemail[e]=r
                    merged=list(byemail.values())
                    list_store_save(mergename.strip(),merged)
                    st.success(f"✅ «{mergename}» créée — {len(merged)} contacts uniques")
                    st.rerun()
        with tB:
            st.markdown("**🧹 Dédupliquer** une base")
            dpick=st.selectbox("Base",names,key="dedup_pick",label_visibility="collapsed")
            if st.button("🧹 Retirer les doublons",use_container_width=True):
                d=[x for x in saved if x["name"]==dpick][0]
                byemail={}
                for r in d["rows"]:
                    e=(r.get("email","") or "").lower().strip()
                    if e and e not in byemail: byemail[e]=r
                before=len(d["rows"]); after=len(byemail)
                list_store_save(dpick,list(byemail.values()))
                st.success(f"✅ «{dpick}» : {before} → {after} ({before-after} doublons retirés)")
                st.rerun()

# ════ 📬 BOÎTE MAIL IMAP ══════════════════════════════════════
elif "📬" in page:
    page_header("Réception", "Boîte mail IMAP", "Inbox · Réponses · Bounces · Emails envoyés")

    # ── Connexion ─────────────────────────────────────────────
    @st.cache_resource(ttl=60)
    def get_imap():
        try:
            m = imap_connect()
            return m, None
        except Exception as e:
            return None, str(e)

    with st.spinner("📡 Connexion IMAP..."):
        mail_conn, conn_err = get_imap()

    if conn_err:
        st.error(f"❌ Connexion IMAP impossible : {conn_err}")
        if st.button("🔄 Réessayer", use_container_width=True):
            st.cache_resource.clear(); st.rerun()
        st.stop()

    # ── Stats mailbox ─────────────────────────────────────────
    stats = get_mailbox_stats(mail_conn)
    c1,c2,c3,c4 = st.columns(4)
    colors = ["#302b63","#238636","#da3633","#8957e5"]
    for col,(lbl,val),clr in zip([c1,c2,c3,c4], stats.items(), colors):
        with col:
            st.markdown(f"""<div class="kpi" style="border-top-color:{clr};">
              <div class="k-label">{lbl}</div>
              <div class="k-val" style="color:{clr};">{val}</div></div>""",
              unsafe_allow_html=True)

    st.markdown("")

    # ── Tabs ──────────────────────────────────────────────────
    tab_inbox, tab_replies, tab_bounces, tab_sent = st.tabs([
        "📨 Inbox", "💬 Réponses reçues", "🔴 Bounces / Échecs", "📤 Envoyés"
    ])

    # ── INBOX ─────────────────────────────────────────────────
    with tab_inbox:
        col_f, col_lim = st.columns([3,1])
        with col_f:
            search_q = st.text_input("🔍 Rechercher dans l'objet ou l'expéditeur",
                                     placeholder="ex: LOGITERRE, reply, invitation...",
                                     label_visibility="collapsed")
        with col_lim:
            limit_n = st.selectbox("Nb emails", [20,50,100,200], label_visibility="collapsed")

        with st.spinner("Chargement..."):
            emails, err = fetch_folder_emails(mail_conn, "INBOX", limit_n)

        if err:
            st.error(f"❌ {err}")
        elif not emails:
            st.info("📭 Inbox vide.")
        else:
            # Filtre recherche
            if search_q:
                emails = [e for e in emails if
                          search_q.lower() in e["subject"].lower() or
                          search_q.lower() in e["from"].lower()]
            st.markdown(f"**{len(emails)} email(s)**")

            for em in emails:
                tag_color = "#f8d7da" if em["bounce"] else ("#d4edda" if em["reply"] else "#f8f9fa")
                tag_text  = "#721c24" if em["bounce"] else ("#155724" if em["reply"] else "#333")
                with st.expander(f"{em['tag']}  **{em['subject'][:60]}**  — *{em['from'][:40]}*  — {em['date'][:16]}"):
                    st.markdown(f"""<div style="background:{tag_color};color:{tag_text};
                      border-radius:8px;padding:.8rem 1rem;font-size:.85rem;
                      font-family:'Courier New',monospace;white-space:pre-wrap;">
<b>De      :</b> {em['from']}
<b>Objet   :</b> {em['subject']}
<b>Date    :</b> {em['date']}
<b>Type    :</b> {em['tag']}

{em['body'] or '(corps vide)'}
                    </div>""",unsafe_allow_html=True)

    # ── RÉPONSES ──────────────────────────────────────────────
    with tab_replies:
        with st.spinner("Analyse des réponses..."):
            all_emails, _ = fetch_folder_emails(mail_conn, "INBOX", 200)
            replies = [e for e in all_emails if e["reply"]]

        if not replies:
            st.info("💬 Aucune réponse à nos invitations détectée dans l'inbox.")
            st.caption("Les réponses contenant 'Re: Official Invitation', 'LOGITERRE', 'Casablanca' etc. apparaîtront ici.")
        else:
            st.success(f"💬 **{len(replies)} réponse(s)** reçue(s) !")
            # Cross-reference avec le log
            log = load_log()
            sent_emails_map = {}
            for k, v in log.items():
                for e in v.get("to", []):
                    sent_emails_map[e.lower()] = k.replace("PRUDENT_","").replace("UMF_","").replace("IFACE_","")

            for em in replies:
                sender_email = EMAIL_RE.search(em["from"])
                sender_str   = sender_email.group(0).lower() if sender_email else ""
                org_name     = sent_emails_map.get(sender_str, "")

                with st.expander(f"💬 **{em['subject'][:60]}** — {em['from'][:45]} — {em['date'][:16]}"):
                    if org_name:
                        st.success(f"✅ Organisation connue : **{org_name}** (dans notre log)")
                    st.markdown(f"""<div style="background:#d4edda;border-radius:8px;
                      padding:.8rem 1rem;font-size:.85rem;white-space:pre-wrap;
                      font-family:'Courier New',monospace;">
<b>De    :</b> {em['from']}
<b>Objet :</b> {em['subject']}
<b>Date  :</b> {em['date']}

{em['body'] or '(corps vide)'}
                    </div>""",unsafe_allow_html=True)

    # ── BOUNCES ───────────────────────────────────────────────
    with tab_bounces:
        with st.spinner("Détection des bounces..."):
            all_emails2, _ = fetch_folder_emails(mail_conn, "INBOX", 200)
            bounces = [e for e in all_emails2 if e["bounce"]]
            # Aussi chercher dans Junk
            junk_emails, _ = fetch_folder_emails(mail_conn, "INBOX.Junk", 50)
            bounces += [e for e in junk_emails if e["bounce"]]

        if not bounces:
            st.success("✅ Aucun bounce détecté — tous les emails semblent avoir été livrés !")
        else:
            st.error(f"🔴 **{len(bounces)} bounce(s) détecté(s)** — emails non livrés")

            # Extrait les adresses qui ont bouncé
            bounced_addrs = []
            for em in bounces:
                found = EMAIL_RE.findall(em["body"])
                for addr in found:
                    if addr.lower() != IMAP_USER.lower() and "mailer" not in addr.lower():
                        bounced_addrs.append(addr.lower())

            if bounced_addrs:
                uniq_bounced=list(set(bounced_addrs))
                st.markdown('<div class="section-title">📋 Adresses en échec</div>',unsafe_allow_html=True)
                df_b = pd.DataFrame({"Email bounced": uniq_bounced})
                st.dataframe(df_b, use_container_width=True, hide_index=True)
                cb1,cb2=st.columns(2)
                with cb1:
                    buf = io.StringIO(); df_b.to_csv(buf, index=False)
                    st.download_button("⬇️ Télécharger CSV",
                        data=buf.getvalue().encode("utf-8"),
                        file_name="bounces_logiterre.csv", mime="text/csv",use_container_width=True)
                with cb2:
                    if st.button("🔄 Marquer comme bounced en DB",use_container_width=True):
                        for addr in uniq_bounced: db.mark_bounced(addr)
                        st.success(f"✅ {len(uniq_bounced)} adresses marquées bounced en base")

            for em in bounces:
                with st.expander(f"🔴 **{em['subject'][:60]}** — {em['date'][:16]}"):
                    st.markdown(f"""<div style="background:#f8d7da;border-radius:8px;
                      padding:.8rem 1rem;font-size:.83rem;white-space:pre-wrap;
                      font-family:'Courier New',monospace;color:#721c24;">
<b>De    :</b> {em['from']}
<b>Objet :</b> {em['subject']}
<b>Date  :</b> {em['date']}

{em['body'] or '(corps vide)'}
                    </div>""",unsafe_allow_html=True)

    # ── ENVOYÉS ───────────────────────────────────────────────
    with tab_sent:
        with st.spinner("Chargement des envoyés..."):
            sent_mails, err_s = fetch_folder_emails(mail_conn, "INBOX.Sent", 100)

        if err_s:
            st.error(f"❌ {err_s}")
        elif not sent_mails:
            st.info("📭 Dossier Envoyés vide.")
        else:
            st.success(f"📤 **{len(sent_mails)}** email(s) envoyés trouvés dans le dossier Sent")
            # Filtre LOGITERRE
            logiterre_sent = [e for e in sent_mails if
                              any(k in e["subject"].lower() for k in ["logiterre","invitation","forum 2026"])]
            other_sent     = [e for e in sent_mails if e not in logiterre_sent]

            if logiterre_sent:
                st.markdown(f'<div class="section-title">🌍 Invitations LOGITERRE ({len(logiterre_sent)})</div>',
                            unsafe_allow_html=True)
                for em in logiterre_sent:
                    with st.expander(f"📤 **{em['subject'][:55]}** — {em['date'][:16]}"):
                        st.markdown(f"""<div style="background:#f0f4ff;border-radius:8px;
                          padding:.8rem 1rem;font-size:.83rem;white-space:pre-wrap;
                          font-family:'Courier New',monospace;">
<b>Objet :</b> {em['subject']}
<b>Date  :</b> {em['date']}
<b>De    :</b> {em['from']}

{em['body'] or '(aperçu non disponible)'}
                        </div>""",unsafe_allow_html=True)

            if other_sent:
                st.markdown(f'<div class="section-title">📨 Autres ({len(other_sent)})</div>',
                            unsafe_allow_html=True)
                df_ot = pd.DataFrame([{
                    "Date": e["date"][:16],
                    "Objet": e["subject"][:60],
                    "De": e["from"][:40]
                } for e in other_sent])
                st.dataframe(df_ot, use_container_width=True, hide_index=True)

    # Refresh button
    st.markdown("---")
    c1, c2 = st.columns([1,4])
    with c1:
        if st.button("🔄 Rafraîchir",use_container_width=True):
            st.cache_resource.clear(); st.rerun()
    with c2:
        st.caption(f"📡 Connecté à **{IMAP_SERVER}:{IMAP_PORT}** — {IMAP_USER}")


# ════ 📊 CAMPAGNES ════════════════════════════════════════════
elif "📊" in page:
    page_header("Organisation", "Gestion des campagnes", "Crée, gère et suis plusieurs campagnes en parallèle")

    tab_list, tab_new = st.tabs(["📋 Mes campagnes", "➕ Nouvelle campagne"])

    with tab_new:
        st.markdown('<div class="section-title">➕ Créer une campagne</div>',unsafe_allow_html=True)
        nc_name=st.text_input("Nom de la campagne",placeholder="ex: Fédérations Europe Q4 2026")
        c1,c2=st.columns(2)
        with c1:
            tpls=[t["name"] for t in db.get_templates()]
            nc_tpl=st.selectbox("Template par défaut",tpls)
        with c2:
            tpl=db.get_template(nc_tpl)
            nc_subj=st.text_input("Objet",value=tpl["subject"] if tpl else "")
        if st.button("✅ Créer la campagne",type="primary",use_container_width=True) and nc_name:
            cid=db.create_campaign(nc_name,nc_subj,nc_tpl)
            st.session_state["active_campaign"]=cid
            st.success(f"✅ Campagne «{nc_name}» créée (ID {cid})")
            st.rerun()

    with tab_list:
        camps=db.get_campaigns()
        if not camps:
            st.info("💡 Aucune campagne. Crée-en une dans l'onglet «Nouvelle campagne».")
        else:
            for c in camps:
                total=c.get("total") or 0; sent=c.get("sent") or 0
                opened=c.get("opened") or 0; replied=c.get("replied") or 0
                pending=c.get("pending") or 0; bounced=c.get("bounced") or 0
                active=st.session_state.get("active_campaign")==c["id"]
                cls="lt-card active" if active else "lt-card"
                badge='<span class="badge-sent" style="margin-left:8px;">ACTIVE</span>' if active else ''
                meta=(f"{total} contacts &nbsp;·&nbsp; {sent} envoyés &nbsp;·&nbsp; {opened} ouverts "
                      f"&nbsp;·&nbsp; {replied} réponses &nbsp;·&nbsp; {bounced} bounces "
                      f"&nbsp;·&nbsp; {pending} en attente")
                H(f"""<div class="{cls}">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                  <div><span class="c-title">{c['name']}</span>{badge}
                  <div class="c-meta">{meta}</div></div>
                  <span class="c-date">{c.get('created','')[:10]}</span></div></div>""")
                cc1,cc2,cc3=st.columns([1,1,4])
                with cc1:
                    if st.button("Activer",key=f"act_{c['id']}",use_container_width=True,
                                 disabled=active):
                        st.session_state["active_campaign"]=c["id"]; st.rerun()
                with cc2:
                    if st.button("Supprimer",key=f"delc_{c['id']}",use_container_width=True):
                        db.delete_campaign(c["id"])
                        if st.session_state.get("active_campaign")==c["id"]:
                            st.session_state["active_campaign"]=None
                        st.rerun()

# ════ 📝 TEMPLATES ════════════════════════════════════════════
elif "📝" in page:
    page_header("Modèles", "Templates d'email", "Modèles adaptés : Académique · Industrie · Gouvernement · Fédération · Relance")

    tpls=db.get_templates()
    tpl_names=[t["name"] for t in tpls]
    sel=st.selectbox("📂 Choisir un template",tpl_names)
    tpl=db.get_template(sel)

    if tpl:
        c1,c2=st.columns([3,1])
        with c1:
            new_subj=st.text_input("📌 Objet",value=tpl["subject"])
        with c2:
            new_type=st.text_input("🏷️ Type",value=tpl.get("type","general"))
        new_body=st.text_area("📝 Corps",value=tpl["body"],height=340)

        c1,c2,c3=st.columns(3)
        with c1:
            if st.button("💾 Sauvegarder ce template",type="primary",use_container_width=True):
                db.save_template(sel,new_subj,new_body,new_type)
                st.success(f"✅ Template «{sel}» mis à jour")
        with c2:
            if st.button("📋 Utiliser dans Composer",use_container_width=True):
                st.session_state["cfg"]["subject"]=new_subj
                st.session_state["cfg"]["body"]=new_body
                st.success("✅ Chargé dans Composer — va à ✍️ Composer")
        with c3:
            st.download_button("⬇️ Exporter",data=f"OBJET: {new_subj}\n\n{new_body}",
                file_name=f"template_{sel}.txt",use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-title">➕ Nouveau template personnalisé</div>',unsafe_allow_html=True)
    nt_name=st.text_input("Nom du nouveau template",placeholder="ex: VIP Speakers")
    nt_subj=st.text_input("Objet du nouveau template")
    nt_body=st.text_area("Corps du nouveau template",height=160,
                         placeholder="Dear ...,\n\n...")
    if st.button("➕ Créer le template",use_container_width=True) and nt_name and nt_body:
        db.save_template(nt_name,nt_subj,nt_body,"custom")
        st.success(f"✅ Template «{nt_name}» créé"); st.rerun()

# ════ 🔄 RELANCES ═════════════════════════════════════════════
elif "🔄" in page:
    page_header("Automatisation", "Relances automatiques", "Relance les contacts qui n'ont pas répondu — +30% de taux de réponse")

    pending=db.get_pending_followups()

    c1,c2,c3=st.columns(3)
    c1.metric("📋 Relances en attente",len(pending))
    # Templates relance
    tpls=db.get_templates()
    fu_tpl=next((t for t in tpls if t.get("type")=="followup"),None)
    c2.metric("📝 Template relance",fu_tpl["name"] if fu_tpl else "—")
    c3.metric("⏱️ Délai configuré",f"J+{cfg.get('followup_days',7)}")

    st.markdown("---")

    if not pending:
        st.info("✅ Aucune relance en attente.")
        st.markdown("""**Comment ça marche :**
1. Active les relances dans **✍️ Composer** (toggle + nombre de jours)
2. Envoie ta campagne normalement
3. Après J+N jours, les contacts **sans réponse** apparaissent ici
4. Clique **Lancer les relances** — ils reçoivent le template de relance""")
    else:
        st.warning(f"🔄 **{len(pending)} contact(s)** à relancer (envoyés, sans réponse, non désinscrits)")

        df_fu=pd.DataFrame([{
            "Organisation":p.get("name","")[:40],
            "Email":p.get("email",""),
            "À relancer depuis":p.get("send_after","")
        } for p in pending])
        st.dataframe(df_fu,use_container_width=True,hide_index=True,height=260)

        # Template de relance
        st.markdown('<div class="section-title">📝 Template de relance</div>',unsafe_allow_html=True)
        fu_subject=st.text_input("Objet de la relance",
            value=fu_tpl["subject"] if fu_tpl else "Following Up: LOGITERRE 2026 – Your Participation")
        fu_body=st.text_area("Corps de la relance",
            value=fu_tpl["body"] if fu_tpl else "Dear Sir/Madam,\n\nWe kindly follow up on our invitation...",
            height=220)

        if st.button(f"🔄 Lancer les {len(pending)} relances",type="primary",use_container_width=True):
            fu_cfg=dict(cfg)
            fu_cfg["subject"]=fu_subject
            fu_cfg["body"]=fu_body
            fu_cfg["followup_enabled"]=False  # pas de relance de relance
            fu_cfg["campaign_id"]=st.session_state.get("active_campaign")
            write_live({"status":"running","total":len(pending),"sent":0,"failed":0,
                        "skipped":0,"current":"Relances...","eta":len(pending)*cfg["delay"],"log":[]})
            write_ctrl("run")
            targets=[{"name":p["name"],"email":p["email"]} for p in pending]
            # Marque les relances comme envoyées
            for p in pending:
                try: db.mark_followup_sent(p["id"])
                except: pass
            t=threading.Thread(target=send_background,args=(targets,fu_cfg),daemon=True)
            t.start()
            st.success(f"✅ {len(targets)} relances lancées — va dans 👁️ Watch Live")
            time.sleep(1); st.rerun()

# ════ 📨 RÉPONSES IA (triage) ═════════════════════════════════
elif "📨" in page:
    page_header("Intelligence", "Triage des réponses", "Classe automatiquement les réponses + génère un brouillon adapté")
    try:
        import reply_triage as rt
    except Exception as e:
        st.error(f"❌ Module triage indisponible : {e}"); st.stop()

    @st.cache_resource(ttl=60)
    def _imap2():
        try: return imap_connect(), None
        except Exception as e: return None, str(e)

    with st.spinner("📡 Lecture des réponses (IMAP)..."):
        conn, err = _imap2()
    if err:
        st.error(f"❌ IMAP : {err}")
        if st.button("🔄 Réessayer"): st.cache_resource.clear(); st.rerun()
        st.stop()

    with st.spinner("Analyse..."):
        inbox, _ = fetch_folder_emails(conn, "INBOX", 200)
        # réponses = celles marquées reply OU non-bounce non-absence avec @ connu
        log = load_log()
        sent_map = {}
        for k,v in log.items():
            for e in v.get("to",[]):
                sent_map[e.lower()] = k.replace("PRUDENT_","").replace("UMF_","").replace("IFACE_","").replace("PRIORITY_","")
        replies = []
        for em in inbox:
            if em["bounce"]: continue
            sender = EMAIL_RE.search(em["from"])
            saddr = sender.group(0).lower() if sender else ""
            # garde si c'est une réponse OU si l'expéditeur est dans notre log
            if em["reply"] or saddr in sent_map:
                tr = rt.triage(em["subject"], em["body"],
                               sender_name=em["from"].split("<")[0].strip(' "'),
                               org_name=sent_map.get(saddr,""))
                replies.append({**em, "addr": saddr, "org": sent_map.get(saddr,""), "tri": tr})

    if not replies:
        st.info("💬 Aucune réponse détectée pour l'instant.")
        st.caption("Les réponses à tes invitations apparaîtront ici, classées automatiquement.")
    else:
        # Stats par catégorie
        from collections import Counter as _C
        cats = _C(r["tri"]["category"] for r in replies)
        cols = st.columns(len(SIGNALS_ORDER := ["interested","needs_info","forwarded","not_interested","out_of_office"]))
        labels = {"interested":"🟢 Intéressés","needs_info":"🔵 Infos","forwarded":"🟣 Transférés",
                  "not_interested":"🔴 Déclins","out_of_office":"🟡 Absences"}
        for col,cat in zip(cols,SIGNALS_ORDER):
            col.metric(labels[cat], cats.get(cat,0))

        st.markdown("---")
        st.success(f"💬 **{len(replies)} réponse(s)** classée(s) automatiquement")

        for i,r in enumerate(replies):
            tri=r["tri"]
            org_disp = r["org"] or r["from"][:40]
            with st.expander(f"{tri['label']}  **{org_disp}** — {r['subject'][:45]} — conf. {tri['confidence']}"):
                st.markdown(f"""<div style="background:#f8f9fa;border-left:4px solid {tri['color']};
                  border-radius:6px;padding:.7rem 1rem;font-size:.84rem;white-space:pre-wrap;
                  font-family:monospace;">
<b>De :</b> {r['from']}
<b>Objet :</b> {r['subject']}
<b>Signaux détectés :</b> {', '.join(tri['signals']) or '—'}

{r['body'][:400]}</div>""",unsafe_allow_html=True)

                if tri["auto_reply"]:
                    st.markdown("**🤖 Brouillon de réponse (modifiable) :**")
                    dsub=st.text_input("Objet",value=tri["draft_subject"],key=f"ds_{i}")
                    dbody=st.text_area("Message",value=tri["draft_body"],height=200,key=f"db_{i}")
                    cc1,cc2=st.columns([1,3])
                    with cc1:
                        if st.button("📤 Envoyer la réponse",key=f"sr_{i}",type="primary",use_container_width=True):
                            try:
                                import send_emails as se, smtplib, ssl as _ssl
                                from email.message import EmailMessage
                                m=EmailMessage()
                                m["From"]=f"{cfg['from_name']} <{cfg['from_email']}>"
                                m["To"]=r["addr"]; m["Reply-To"]=cfg["reply_to"]
                                m["Subject"]=dsub; m.set_content(dbody)
                                ctx=_ssl._create_unverified_context()
                                with smtplib.SMTP_SSL(se.SMTP_SERVER,se.SMTP_PORT,context=ctx,timeout=30) as s:
                                    s.login(se.SMTP_USER,se.SMTP_PASSWORD)
                                    s.send_message(m)
                                st.success(f"✅ Réponse envoyée à {r['addr']}")
                            except Exception as ex:
                                st.error(f"❌ {ex}")
                    with cc2:
                        st.caption(f"Réponse en **{tri['lang'].upper()}** · catégorie **{tri['category']}**")
                else:
                    st.info("🟡 Absence automatique détectée — aucune réponse nécessaire.")

    st.markdown("---")
    if st.button("🔄 Rafraîchir les réponses",use_container_width=True):
        st.cache_resource.clear(); st.rerun()

# ════ ✅ INSCRIPTIONS RSVP ════════════════════════════════════
elif "✅" in page:
    page_header("Conversion", "Inscriptions & RSVP", "Qui vient vraiment — le KPI qui compte")

    # Source : Supabase (cloud persistant) si configuré, sinon SQLite local
    if supa.enabled():
        rsvps = supa.get_rsvps()
        st.caption("🟢 Données : Supabase (persistant, cloud)")
        def _cnt(r): return sum(1 for x in rsvps if x.get("response")==r)
        rstats = {"total":len(rsvps), "yes":_cnt("yes"), "maybe":_cnt("maybe"), "no":_cnt("no"),
                  "total_delegates":sum(int(x.get("delegates",0) or 0) for x in rsvps if x.get("response")=="yes"),
                  "speakers":sum(1 for x in rsvps if x.get("speaker"))}
    else:
        rstats=db.get_rsvp_stats()
        rsvps=db.get_rsvps()

    # Funnel global : invités → envoyés → ouverts → réponses → inscrits oui
    log=load_log()
    n_sent=total_sent()
    opens=db.get_opens()
    n_open=len(opens)
    n_rsvp=rstats.get("total",0) or 0
    n_yes=rstats.get("yes",0) or 0

    c1,c2,c3,c4,c5=st.columns(5)
    for col,(v,l,clr) in zip([c1,c2,c3,c4,c5],[
        (n_sent,"Invités","#302b63"),(n_open,"Ouvert","#d29922"),
        (n_rsvp,"Réponses RSVP","#1f6feb"),(n_yes,"✅ Confirmés","#238636"),
        (rstats.get("total_delegates",0) or 0,"Délégués","#8957e5")]):
        with col: st.markdown(f"""<div class="kpi" style="border-top-color:{clr};">
          <div class="k-label">{l}</div><div class="k-val" style="color:{clr};">{v}</div></div>""",
          unsafe_allow_html=True)

    st.markdown("")
    # Tunnel visuel
    st.markdown('<div class="section-title">🔻 Tunnel de conversion</div>',unsafe_allow_html=True)
    funnel=pd.DataFrame({"Étape":["Invités","Ouvert","RSVP reçus","Confirmés ✅"],
                         "Nombre":[n_sent,n_open,n_rsvp,n_yes]})
    st.bar_chart(funnel.set_index("Étape"),color="#238636",height=240)

    if n_sent>0:
        conv=n_yes*100//max(n_sent,1)
        st.info(f"📊 Taux de conversion invité→confirmé : **{conv}%** · "
                f"{rstats.get('speakers',0) or 0} intervenant(s) potentiel(s)")

    st.markdown("---")
    if not rsvps:
        st.info("💡 Aucune inscription pour l'instant.")
        st.markdown("""**Comment ça marche :**
1. Active le **tracking** (Composer → URL serveur) — un bouton *Confirm your participation* est ajouté à chaque email
2. Le destinataire clique → remplit le formulaire (oui/non + nb délégués)
3. Les réponses apparaissent ici en temps réel 🎯""")
    else:
        st.markdown('<div class="section-title">📋 Réponses reçues</div>',unsafe_allow_html=True)
        df_r=pd.DataFrame([{
            "Réponse":{"yes":"✅ Oui","maybe":"🤔 Peut-être","no":"❌ Non"}.get(r["response"],r["response"]),
            "Organisation":r.get("org_name","")[:40],
            "Email":r.get("email",""),
            "Délégués":r.get("delegates",0),
            "Speaker":"🎤" if r.get("speaker") else "",
            "Message":(r.get("notes","") or "")[:50],
            "Date":r.get("created","")[:16],
        } for r in rsvps])
        st.dataframe(df_r,use_container_width=True,hide_index=True,height=320)
        # Export confirmés
        confirmed=[r for r in rsvps if r["response"]=="yes"]
        if confirmed:
            buf=io.StringIO()
            pd.DataFrame(confirmed)[["org_name","email","delegates","speaker","notes"]].to_csv(buf,index=False)
            st.download_button("⬇️ Exporter les confirmés (CSV)",data=buf.getvalue().encode("utf-8-sig"),
                file_name="confirmes_logiterre.csv",mime="text/csv",use_container_width=True)

# ════ 📡 DÉLIVRABILITÉ (SMTP · warmup · suppression · bounces) ════
elif "📡" in page:
    page_header("Réputation", "Délivrabilité",
                "Serveur d'envoi · montée en charge (warmup) · liste de suppression · bounces")
    import datetime as _dt

    tab_smtp, tab_warm, tab_supp, tab_bounce = st.tabs(
        ["📤 Serveur SMTP", "🔥 Warmup", "🛡️ Suppression", "🔴 Scan bounces"])

    # ── 1) SMTP configurable ──────────────────────────────────
    with tab_smtp:
        st.caption("Par défaut : Hostinger. Pour booster la délivrabilité tu peux brancher un "
                   "ESP dédié (Brevo, SendGrid, Amazon SES, Mailgun…) — IP à meilleure réputation.")
        PRESETS={"Hostinger (défaut)":("smtp.hostinger.com",465),
                 "Brevo (Sendinblue)":("smtp-relay.brevo.com",587),
                 "SendGrid":("smtp.sendgrid.net",587),
                 "Amazon SES (eu-west-1)":("email-smtp.eu-west-1.amazonaws.com",587),
                 "Mailgun":("smtp.mailgun.org",587),
                 "Gmail / Google Workspace":("smtp.gmail.com",587)}
        pc1,pc2=st.columns([2,1])
        with pc1:
            preset=st.selectbox("Préréglage fournisseur",list(PRESETS.keys()))
        with pc2:
            if st.button("Appliquer le préréglage",use_container_width=True):
                cfg["smtp_server"],cfg["smtp_port"]=PRESETS[preset]; st.rerun()
        s1,s2=st.columns(2)
        with s1:
            cfg["smtp_server"]=st.text_input("Serveur SMTP",value=cfg.get("smtp_server","smtp.hostinger.com"))
            cfg["smtp_user"]=st.text_input("Identifiant SMTP",value=cfg.get("smtp_user",""),
                placeholder="(vide = compte Hostinger par défaut)")
            cfg["smtp_from"]=st.text_input("Adresse expéditeur (From)",value=cfg.get("smtp_from",""),
                placeholder="(vide = identifiant SMTP)")
        with s2:
            cfg["smtp_port"]=st.number_input("Port",value=int(cfg.get("smtp_port",465)),step=1,
                help="465 = SSL (Hostinger) · 587 = STARTTLS (la plupart des ESP)")
            cfg["smtp_password"]=st.text_input("Mot de passe / clé SMTP",value=cfg.get("smtp_password",""),
                type="password",placeholder="(vide = secret Hostinger configuré)")
        prov = "STARTTLS" if int(cfg.get("smtp_port",465))==587 else "SSL"
        st.info(f"📤 Envoi via **{cfg.get('smtp_server')}**:{int(cfg.get('smtp_port',465))} ({prov}) · "
                f"{'identifiant personnalisé' if cfg.get('smtp_user') else 'compte Hostinger par défaut'}")
        st.caption("💡 Astuce : un ESP dédié (SES/Brevo) sur ton domaine authentifié = la plus grosse "
                   "amélioration possible de délivrabilité (IP réputée + volume élevé).")

    # ── 2) Warmup ─────────────────────────────────────────────
    with tab_warm:
        st.caption("Le warmup protège ta réputation : on commence petit et on augmente le volume "
                   "autorisé chaque jour (×1,5/jour). Indispensable pour un domaine jeune (Outlook).")
        if not supa.enabled():
            st.warning("Le warmup persistant nécessite Supabase configuré (Secrets).")
        else:
            w=supa.get_warmup() or {}
            wc1,wc2,wc3=st.columns(3)
            with wc1:
                active=st.toggle("🔥 Warmup activé",value=bool(w.get("active",False)))
            with wc2:
                d0=st.number_input("Volume jour 1",min_value=5,max_value=500,
                    value=int(w.get("day0_limit",20) or 20),step=5)
            with wc3:
                sd_default=_dt.date.fromisoformat(str(w["start_date"])[:10]) if w.get("start_date") else _dt.date.today()
                start=st.date_input("Date de début",value=sd_default)
            if st.button("💾 Enregistrer le warmup",type="primary"):
                supa.set_warmup(start.isoformat(),d0,active); st.success("Warmup enregistré ✅"); st.rerun()
            # Aperçu de la montée en charge
            if w.get("active") and w.get("start_date"):
                tl=warmup_today_limit()
                st.markdown(f"""<div style="background:linear-gradient(135deg,#d2691e14,#d2691e05);
                  border:1px solid #d2691e33;border-radius:12px;padding:1rem;margin-top:.6rem;">
                  <div style="font-size:.7rem;opacity:.6;text-transform:uppercase;">Limite autorisée aujourd'hui</div>
                  <div style="font-size:2rem;font-weight:800;color:#d2691e;">{tl} emails</div>
                  <div style="font-size:.75rem;opacity:.7;">déjà envoyés aujourd'hui : {messages_today()} · plafond plan : {cfg.get('plan_limit',1000)}</div>
                  </div>""",unsafe_allow_html=True)
                # planning 10 jours
                base=int(w.get("day0_limit",20) or 20)
                sched=[{"Jour":f"J+{n}","Date":(_dt.date.fromisoformat(str(w['start_date'])[:10])+_dt.timedelta(days=n)).isoformat(),
                        "Limite/jour":min(cfg.get('plan_limit',1000),round(base*(1.5**n)))} for n in range(0,11)]
                st.dataframe(pd.DataFrame(sched),use_container_width=True,hide_index=True,height=240)
            else:
                st.info("Active le warmup et enregistre pour voir le planning de montée en charge.")

    # ── 3) Liste de suppression ───────────────────────────────
    with tab_supp:
        st.caption("Adresses à ne JAMAIS recontacter (bounces, plaintes, blocage manuel). "
                   "Elles sont automatiquement ignorées à l'envoi — protège ta réputation.")
        if not supa.enabled():
            st.warning("La liste de suppression persistante nécessite Supabase (Secrets).")
        else:
            ac1,ac2=st.columns([3,1])
            with ac1:
                new_supp=st.text_input("Ajouter une adresse à supprimer",placeholder="email@exemple.com")
            with ac2:
                st.markdown("<div style='height:1.8rem'></div>",unsafe_allow_html=True)
                if st.button("➕ Supprimer",use_container_width=True) and new_supp.strip():
                    supa.add_suppression(new_supp.strip(),"manual"); st.rerun()
            sup=supa.get_suppressions()
            uns=supa.get_unsubs()
            m1,m2=st.columns(2)
            m1.metric("🛡️ Supprimées (bounce/manuel)",len(sup))
            m2.metric("🚫 Désinscrites (RGPD)",len(uns))
            if sup:
                df=pd.DataFrame([{"Email":s.get("email",""),"Raison":s.get("reason","manual"),
                    "Note":s.get("note",""),"Date":(s.get("created","") or "")[:16]} for s in sup])
                st.dataframe(df,use_container_width=True,hide_index=True,height=300)
                cbuf=io.StringIO(); df.to_csv(cbuf,index=False)
                st.download_button("⬇️ Exporter (CSV)",cbuf.getvalue().encode("utf-8-sig"),
                    "suppression_logiterre.csv","text/csv")
                rm=st.text_input("Réhabiliter une adresse (retirer de la liste)",placeholder="email@exemple.com")
                if st.button("♻️ Retirer de la suppression") and rm.strip():
                    supa.remove_suppression(rm.strip()); st.success(f"{rm} réhabilitée"); st.rerun()
            else:
                st.success("Aucune adresse supprimée. 👍")

    # ── 4) Scan des bounces (IMAP) ────────────────────────────
    with tab_bounce:
        st.caption("Scanne ta boîte IMAP, détecte les emails de bounce (échec de livraison) et "
                   "ajoute automatiquement les adresses mortes à la liste de suppression.")
        if not IMAP_PASSWORD:
            st.warning("Configure IMAP (mot de passe) pour scanner les bounces.")
        else:
            scan_n=st.slider("Nombre d'emails récents à scanner",20,300,100,20)
            if st.button("🔍 Scanner les bounces maintenant",type="primary"):
                with st.spinner("Connexion IMAP + analyse…"):
                    try:
                        mail=imap_connect()
                        items,err=fetch_folder_emails(mail,"INBOX",limit=scan_n,search="ALL")
                        try: mail.logout()
                        except Exception: pass
                        if err:
                            st.error(f"Erreur IMAP : {err}")
                        else:
                            own={"logiterre-expo.com","uaotlafrica.com"}
                            found=set()
                            email_re=re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
                            for it in items:
                                if not it.get("bounce"): continue
                                for cand in email_re.findall(it.get("body","")+" "+it.get("subject","")):
                                    cl=cand.lower().strip(".,;:<>()[]")
                                    if cl.split("@")[-1] in own: continue
                                    if "mailer-daemon" in cl or "postmaster" in cl: continue
                                    found.add(cl)
                            added=0
                            if supa.enabled():
                                for e in found:
                                    if supa.add_suppression(e,"bounce","détecté via scan IMAP"): added+=1
                            n_bounce=sum(1 for it in items if it.get("bounce"))
                            st.success(f"✅ Scan terminé : {n_bounce} bounce(s) trouvé(s) · "
                                       f"{len(found)} adresse(s) extraite(s) · {added} ajoutée(s) à la suppression.")
                            if found:
                                st.dataframe(pd.DataFrame(sorted(found),columns=["Adresse en bounce (supprimée)"]),
                                    use_container_width=True,hide_index=True,height=240)
                    except Exception as e:
                        st.error(f"❌ {type(e).__name__}: {e}")

# ════ 🎯 ENGAGEMENT (tracking ouvreurs / cliqueurs / désinscrits) ══
elif "🎯" in page:
    page_header("Tracking", "Engagement", "Qui a ouvert · qui a cliqué · qui s'est désinscrit — par email")

    rows, S = engagement_data()

    if not supa.enabled():
        st.warning("⚠️ Supabase n'est pas configuré : le tracking par email (ouvertures/clics/désinscriptions) "
                   "fonctionne en mode local seulement. Configure SUPABASE_URL + SUPABASE_KEY dans les Secrets "
                   "pour un suivi persistant sur le cloud.")

    if not rows:
        st.info("Aucune donnée d'engagement pour l'instant. Envoie des invitations puis reviens ici : "
                "tu verras qui ouvre, qui clique et qui se désinscrit, en temps réel.")
    else:
        # ── KPI funnel band ───────────────────────────────────────
        def _bigtile(col,label,val,sub,clr):
            with col: st.markdown(f"""<div style="background:linear-gradient(135deg,{clr}14,{clr}05);
              border:1px solid {clr}33;border-left:4px solid {clr};border-radius:12px;padding:.9rem 1rem;">
              <div style="font-size:.62rem;letter-spacing:.06em;text-transform:uppercase;opacity:.6;">{label}</div>
              <div style="font-size:1.9rem;font-weight:800;color:{clr};line-height:1.1;">{val}</div>
              <div style="font-size:.7rem;opacity:.65;">{sub}</div></div>""",unsafe_allow_html=True)
        c1,c2,c3,c4,c5=st.columns(5)
        _bigtile(c1,"📤 Envoyés",  S["sent"],  "contacts touchés",            "#6d5ee0")
        _bigtile(c2,"📨 Ouvreurs", S["open"],  f"{S['open_rate']}% taux d'ouverture","#3d9be0")
        _bigtile(c3,"🖱️ Cliqueurs",S["click"], f"{S['click_rate']}% · CTR {S['ctr']}%","#d2691e")
        _bigtile(c4,"✅ Répondus", S["reply"], f"{S['yes']} confirmés",        "#0f8a4f")
        _bigtile(c5,"🚫 Désinscrits",S["unsub"],"opt-out RGPD",                "#c8362f")

        # ── Funnel barre horizontale ─────────────────────────────
        st.markdown("")
        def _fbar(label,val,base,clr):
            pct=int(val/max(base,1)*100)
            return (f'<div style="display:flex;align-items:center;gap:.7rem;margin:.28rem 0;">'
                    f'<span style="width:120px;font-size:.8rem;opacity:.8;text-align:right;">{label}</span>'
                    f'<span style="flex:1;background:rgba(128,128,128,.13);border-radius:6px;height:22px;overflow:hidden;">'
                    f'<span style="display:block;height:100%;width:{pct}%;background:{clr};border-radius:6px;"></span></span>'
                    f'<span style="width:70px;font-size:.82rem;font-weight:700;">{val} · {pct}%</span></div>')
        H('<div class="panel"><div class="panel-title">🔻 Entonnoir d\'engagement</div>'
          +_fbar("Envoyés",S["sent"],S["sent"],"#6d5ee0")
          +_fbar("Ouvreurs",S["open"],S["sent"],"#3d9be0")
          +_fbar("Cliqueurs",S["click"],S["sent"],"#d2691e")
          +_fbar("Répondus",S["reply"],S["sent"],"#0f8a4f")
          +_fbar("Confirmés",S["yes"],S["sent"],"#0a6e3e")
          +'</div>')

        # ── Filtre + recherche ───────────────────────────────────
        st.markdown("---")
        fc1,fc2=st.columns([2,3])
        with fc1:
            seg=st.radio("Filtrer",["🌍 Tous","📨 Ouvreurs","🖱️ Cliqueurs","✅ Répondus",
                                     "🚫 Désinscrits","❄️ Jamais ouvert"],horizontal=False)
        with fc2:
            q=st.text_input("🔎 Rechercher (email ou organisation)","").lower().strip()

        def _keep(r):
            if seg=="📨 Ouvreurs"      and not r["opens"]>0: return False
            if seg=="🖱️ Cliqueurs"    and not r["clicks"]>0: return False
            if seg=="✅ Répondus"      and not r["replied"]: return False
            if seg=="🚫 Désinscrits"   and not r["unsub"]: return False
            if seg=="❄️ Jamais ouvert" and not (r["sent"] and r["opens"]==0 and not r["unsub"]): return False
            if q and q not in r["email"] and q not in (r["org"] or "").lower(): return False
            return True
        view=[r for r in rows if _keep(r)]

        st.markdown(f"<div style='font-size:.8rem;opacity:.6;margin:.3rem 0;'>{len(view)} contact(s) affiché(s)</div>",
                    unsafe_allow_html=True)

        # ── Tableau unifié (le parcours de chaque contact) ───────
        def _ic(b): return "✅" if b else "·"
        tdf=pd.DataFrame([{
            "Grade":r["grade"],
            "Organisation":r["org"] or "—",
            "Email":r["email"],
            "📤":_ic(r["sent"]),
            "📨 Ouvert":(f'{r["opens"]}×' if r["opens"] else "·"),
            "🖱️ Cliqué":(f'{r["clicks"]}×' if r["clicks"] else "·"),
            "✅ Répondu":({"yes":"✅ Oui","no":"❌ Non"}.get(r["response"],"·") if r["replied"] else "·"),
            "🚫":("🚫" if r["unsub"] else "·"),
            "Dernière activité":(r["click_at"] or r["open_at"] or r["sent_at"] or ""),
        } for r in view])
        st.dataframe(tdf,use_container_width=True,hide_index=True,height=460,
            column_config={"Grade":st.column_config.TextColumn(width="small"),
                           "Email":st.column_config.TextColumn(width="medium")})

        # ── Export CSV complet ───────────────────────────────────
        buf=io.StringIO()
        pd.DataFrame([{"organisation":r["org"],"email":r["email"],"grade":r["grade"],
            "score":r["score"],"envoye":r["sent"],"ouvertures":r["opens"],"clics":r["clicks"],
            "repondu":r["replied"],"reponse":r["response"],"delegues":r["delegates"],
            "desinscrit":r["unsub"],"raison_desinscription":r["unsub_reason"],
            "envoye_le":r["sent_at"],"premiere_ouverture":r["open_at"],
            "premier_clic":r["click_at"]} for r in view]).to_csv(buf,index=False)
        st.download_button("⬇️ Exporter cette vue (CSV complet)",buf.getvalue().encode("utf-8-sig"),
            "engagement_logiterre.csv","text/csv",use_container_width=True)

        # ── 3 listes ciblées : ouvreurs / cliqueurs / désinscrits ─
        st.markdown("---")
        st.markdown('<div class="section-title">🎯 Listes d\'action</div>',unsafe_allow_html=True)
        t1,t2,t3=st.tabs([f"🖱️ Cliqueurs ({S['click']})",
                          f"📨 Ouvreurs non-cliqueurs ({sum(1 for r in rows if r['opens']>0 and r['clicks']==0 and not r['unsub'])})",
                          f"🚫 Désinscrits ({S['unsub']})"])
        with t1:
            st.caption("Tes contacts les plus chauds — ils ont cliqué le lien. À relancer en priorité.")
            hot=[r for r in rows if r["clicks"]>0]
            if hot:
                st.dataframe(pd.DataFrame([{"Organisation":r["org"] or "—","Email":r["email"],
                    "Clics":r["clicks"],"A répondu":("✅" if r["replied"] else "—"),
                    "Date":r["click_at"]} for r in hot]),use_container_width=True,hide_index=True)
            else: st.caption("Aucun clic pour l'instant.")
        with t2:
            st.caption("Ils ont ouvert mais pas encore cliqué — un rappel ciblé peut les convertir.")
            warm=[r for r in rows if r["opens"]>0 and r["clicks"]==0 and not r["unsub"]]
            if warm:
                st.dataframe(pd.DataFrame([{"Organisation":r["org"] or "—","Email":r["email"],
                    "Ouvertures":r["opens"],"Date":r["open_at"]} for r in warm]),
                    use_container_width=True,hide_index=True)
                wbuf=io.StringIO()
                pd.DataFrame([{"organisation":r["org"],"email":r["email"]} for r in warm]).to_csv(wbuf,index=False)
                st.download_button("⬇️ Liste de relance (CSV)",wbuf.getvalue().encode("utf-8-sig"),
                    "relance_ouvreurs.csv","text/csv")
            else: st.caption("Personne dans ce segment.")
        with t3:
            st.caption("Désinscrits — NE PAS recontacter (conformité RGPD).")
            outs=[r for r in rows if r["unsub"]]
            if outs:
                st.dataframe(pd.DataFrame([{"Organisation":r["org"] or "—","Email":r["email"],
                    "Raison":r["unsub_reason"] or "—"} for r in outs]),
                    use_container_width=True,hide_index=True)
            else: st.caption("Aucune désinscription. 👍")

# ════ 📈 ANALYTICS & RAPPORT ══════════════════════════════════
elif "📈" in page:
    page_header("Rapports", "Analytics & Rapport", "Entonnoir de conversion · Taux d'ouverture · Rapport professionnel")

    # Source des données : DB campaign OU log global
    camps=db.get_campaigns()
    source=st.radio("Source des données",
                    ["📊 Campagne DB","🌍 Toute la campagne (log global)"],horizontal=True)

    if source.startswith("📊") and camps:
        cnames={c["name"]:c["id"] for c in camps}
        sel=st.selectbox("Campagne",list(cnames.keys()))
        cid=cnames[sel]
        stats=db.get_campaign_stats(cid)
        contacts=db.get_contacts(cid)
        camp_name=sel
    else:
        # Depuis le log global
        log=load_log()
        sent_all=[(k,v) for k,v in log.items() if v.get("status")=="sent"]
        stats={"total":len(sent_all),"sent":len(sent_all),"opened":0,"replied":0,
               "bounced":0,"pending":0,"unsub":len(db.get_unsubscribes())}
        contacts=[{"name":k.replace("PRUDENT_","").replace("UMF_","").replace("IFACE_","").replace("PRIORITY_",""),
                   "email":v.get("to",["?"])[0],
                   "org_type":db.detect_org_type(k,v.get("to",["?"])[0]),
                   "replied_at":None} for k,v in sent_all]
        camp_name="LOGITERRE 2026 — Campagne Globale"

    # KPIs
    total=stats.get("total",0); sent=stats.get("sent",0)
    opened=stats.get("opened",0); replied=stats.get("replied",0); bounced=stats.get("bounced",0)
    c1,c2,c3,c4,c5=st.columns(5)
    metrics=[(total,"Contacts","#302b63"),(sent,"Envoyés","#238636"),
             (f"{(sent-bounced)*100//max(sent,1)}%","Livraison","#1f6feb"),
             (f"{opened*100//max(sent,1)}%","Ouverture","#d29922"),
             (f"{replied*100//max(sent,1)}%","Réponse","#8957e5")]
    for col,(v,l,clr) in zip([c1,c2,c3,c4,c5],metrics):
        with col: st.markdown(f"""<div class="kpi" style="border-top-color:{clr};">
          <div class="k-label">{l}</div><div class="k-val" style="color:{clr};">{v}</div></div>""",
          unsafe_allow_html=True)

    st.markdown("")
    # Funnel chart
    st.markdown('<div class="section-title">🔻 Entonnoir de conversion</div>',unsafe_allow_html=True)
    funnel=pd.DataFrame({
        "Étape":["Ciblés","Envoyés","Livrés","Ouverts","Réponses"],
        "Nombre":[total,sent,sent-bounced,opened,replied]
    })
    st.bar_chart(funnel.set_index("Étape"),color="#302b63",height=240)

    # ── Détail engagement : qui a OUVERT / qui a CLIQUÉ ───────
    st.markdown("---")
    st.markdown('<div class="section-title">📨 Qui a ouvert / cliqué</div>',unsafe_allow_html=True)
    if supa.enabled():
        opens_l = supa.get_opens()
        clicks_l = supa.get_clicks()
        rsvps_l = supa.get_rsvps()
        eo,ec = st.columns(2)
        with eo:
            st.markdown(f"**📨 Ouvertures ({len(opens_l)})**")
            if opens_l:
                st.dataframe(pd.DataFrame([{"Email":o.get("email",""),
                    "Organisation":o.get("org_name",""),"Date":(o.get("created","") or "")[:16]}
                    for o in opens_l]),use_container_width=True,hide_index=True,height=260)
            else: st.caption("Aucune ouverture pour l'instant.")
        with ec:
            st.markdown(f"**🖱️ Clics sur le bouton ({len(clicks_l)})**")
            if clicks_l:
                rsvp_emails={r.get("email","").lower() for r in rsvps_l}
                st.dataframe(pd.DataFrame([{"Email":c.get("email",""),
                    "Organisation":c.get("org_name",""),
                    "A répondu":"✅" if c.get("email","").lower() in rsvp_emails else "—",
                    "Date":(c.get("created","") or "")[:16]}
                    for c in clicks_l]),use_container_width=True,hide_index=True,height=260)
            else: st.caption("Aucun clic pour l'instant.")
        # Export
        if opens_l or clicks_l:
            import io as _io
            buf=_io.StringIO()
            pd.DataFrame([{"type":"open","email":o.get("email",""),"org":o.get("org_name",""),
                "date":o.get("created","")} for o in opens_l]+
                [{"type":"click","email":c.get("email",""),"org":c.get("org_name",""),
                "date":c.get("created","")} for c in clicks_l]).to_csv(buf,index=False)
            st.download_button("⬇️ Exporter ouvertures + clics (CSV)",buf.getvalue().encode("utf-8-sig"),
                "engagement_logiterre.csv","text/csv")
    else:
        st.info("Le détail par email (ouvertures/clics) nécessite Supabase configuré (Secrets).")

    # Répartition par type
    type_counts=Counter(c.get("org_type","general") for c in contacts)
    if type_counts:
        st.markdown('<div class="section-title">🏛️ Répartition par type</div>',unsafe_allow_html=True)
        tdf=pd.DataFrame(sorted(type_counts.items(),key=lambda x:-x[1]),columns=["Type","Contacts"])
        st.bar_chart(tdf.set_index("Type"),color="#1f6feb",height=220)

    # PDF Report
    st.markdown("---")
    st.markdown('<div class="section-title">📄 Rapport PDF professionnel</div>',unsafe_allow_html=True)
    if HAS_REPORT:
        st.caption("Génère un rapport PDF prêt à présenter aux sponsors, partenaires ou direction.")
        if st.button("📄 Générer le rapport PDF",type="primary",use_container_width=True):
            with st.spinner("Génération..."):
                pdf=report_gen.generate_campaign_report(camp_name,stats,contacts)
            if pdf:
                st.success("✅ Rapport généré !")
                st.download_button("⬇️ Télécharger le rapport PDF",data=pdf,
                    file_name=f"Rapport_{safe_fn(camp_name)}.pdf",mime="application/pdf",
                    use_container_width=True)
            else:
                st.error("❌ reportlab non disponible")
    else:
        st.warning("⚠️ Module reportlab manquant. Installe : `pip install reportlab`")


# ════ ⚙️ PARAMÈTRES ═══════════════════════════════════════════
elif "⚙️" in page:
    page_header("Configuration", "Paramètres", "SMTP · Limites · Export · Nettoyage")
    tab1,tab2,tab3,tab4=st.tabs(["🔌 SMTP","📡 Tracking","⚠️ Limites Hostinger","📥 Export"])
    with tab1:
        st.markdown('<div class="section-title">🔌 Connexion Hostinger</div>',unsafe_allow_html=True)
        c1,c2=st.columns(2)
        with c1:
            st.text_input("Serveur","smtp.hostinger.com",disabled=True)
            st.text_input("Port","465 — SSL",disabled=True)
        with c2:
            st.text_input("Utilisateur","a.zahraoui@logiterre-expo.com",disabled=True)
            st.text_input("SSL","✅ Certificat désactivé (mode compatibilité)",disabled=True)
        st.markdown("")
        if st.button("🔌 Tester la connexion SMTP",use_container_width=True,type="primary"):
            with st.spinner("Test..."):
                try:
                    import smtplib,ssl as ssl_t, send_emails as se
                    if not se.SMTP_PASSWORD:
                        st.error("❌ Aucun mot de passe configuré (Secrets / .streamlit/secrets.toml)")
                    else:
                        ctx=ssl_t._create_unverified_context()
                        with smtplib.SMTP_SSL(se.SMTP_SERVER,se.SMTP_PORT,context=ctx,timeout=15) as s:
                            s.login(se.SMTP_USER,se.SMTP_PASSWORD)
                        st.success("✅ Connexion OK — SMTP prêt !")
                except Exception as e: st.error(f"❌ {e}")
        st.markdown("---")
        st.markdown("""**Si Hostinger bloque :**
1. Va sur [hPanel Hostinger](https://hpanel.hostinger.com)
2. Emails → ton compte → **Réactiver**
3. Attends 5-10 minutes puis reteste""")
    with tab2:
        st.markdown('<div class="section-title">📡 Tracking</div>',unsafe_allow_html=True)
        IS_CLOUD = str(BASE_DIR).startswith("/mount") or not Path(PYTHON).exists()

        # État RSVP (Supabase) — le tracking principal
        if supa.enabled():
            st.success("🟢 Tracking RSVP ACTIF (Supabase) — qui confirme sa venue est enregistré, "
                       "en ligne, sans serveur local.")
        else:
            st.info("RSVP local (SQLite). Configure Supabase pour le RSVP persistant en ligne.")

        st.markdown("---")
        st.markdown('<div class="section-title">👁️ Pixel d\'ouverture (optionnel)</div>',unsafe_allow_html=True)

        if IS_CLOUD:
            st.info("☁️ Sur Streamlit Cloud, le serveur de pixel ne peut pas tourner ici. "
                    "Le **RSVP** (ci-dessus) couvre l'essentiel. Pour le pixel d'ouverture, "
                    "lance `tracking_server.py` + un tunnel depuis une machine, puis colle l'URL "
                    "dans Composer.")
        else:
            import socket
            def _port_open(p):
                s=socket.socket(socket.AF_INET,socket.SOCK_STREAM); s.settimeout(0.5)
                try: return s.connect_ex(("127.0.0.1",p))==0
                finally: s.close()
            running=_port_open(8765)
            st.success("🟢 Serveur pixel ACTIF (localhost:8765)") if running else st.warning("🔴 Serveur pixel arrêté")
            c1,c2=st.columns(2)
            with c1:
                if st.button("▶️ Démarrer le serveur pixel",use_container_width=True,disabled=running):
                    import subprocess as sp, sys as _sys
                    sp.Popen([_sys.executable, str(BASE_DIR/"tracking_server.py"),"8765"],
                             stdout=sp.DEVNULL,stderr=sp.DEVNULL)
                    time.sleep(2); st.rerun()
            with c2:
                if st.button("⏹️ Arrêter",use_container_width=True,disabled=not running):
                    subprocess.run(["pkill","-f","tracking_server.py"]); time.sleep(1); st.rerun()

        st.markdown("---")
        st.markdown('<div class="section-title">👁️ Ouvertures détectées</div>',unsafe_allow_html=True)
        try:
            opens = supa.get_opens() if supa.enabled() else db.get_opens()
        except Exception:
            opens = []
        if opens:
            st.success(f"👁️ **{len(opens)}** ouverture(s) enregistrée(s)")
            df_o=pd.DataFrame([{"Organisation":o.get("org_name") or o.get("name",""),
                                "Email":o.get("email",""),
                                "Ouvert le":o.get("created") or o.get("opened_at","")} for o in opens])
            st.dataframe(df_o,use_container_width=True,hide_index=True,height=240)
        else:
            st.info("Aucune ouverture détectée pour l'instant.")

    with tab3:
        st.markdown('<div class="section-title">📊 Quota Hostinger — aujourd\'hui</div>',unsafe_allow_html=True)

        # Sélecteur de plan
        plan_names=list(PLAN_LIMITS.keys())
        cur_limit=cfg.get("plan_limit",100)
        cur_idx=next((i for i,n in enumerate(plan_names) if PLAN_LIMITS[n]==cur_limit),0)
        sel_plan=st.selectbox("Ton plan email Hostinger",plan_names,index=cur_idx)
        cfg["plan_limit"]=PLAN_LIMITS[sel_plan]
        limit=cfg["plan_limit"]

        # Jauge live : messages envoyés aujourd'hui (To + CC)
        used=messages_today()
        cc_n=len([x for x in cfg.get("cc","").split(",") if x.strip()])
        per_send=1+cc_n
        pct=min(int(used/max(limit,1)*100),100)
        bar_color="#0f8a4f" if pct<70 else ("#b9770b" if pct<90 else "#c8362f")
        remaining=max(limit-used,0)
        sends_left=remaining//per_send

        H(f"""<div class="panel">
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
          <span style="font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;">
            Messages envoyés aujourd'hui</span>
          <span style="font-family:'Fraunces',serif;font-size:1.5rem;font-weight:600;">{used} / {limit}</span></div>
        <div class="prog-wrap" style="height:14px;margin:.7rem 0;">
          <div class="prog-fill" style="width:{pct}%;background:{bar_color};"></div></div>
        <div style="font-size:.84rem;color:var(--ink-2);">
          Il te reste <b>{remaining}</b> messages → soit <b>~{sends_left} envois</b>
          (chaque envoi = 1 destinataire + {cc_n} CC = <b>{per_send} messages</b>)</div>
        </div>""")

        cfg["daily_guard"]=st.toggle("🛡️ Arrêt automatique avant de dépasser le quota",
            value=cfg.get("daily_guard",True),
            help="Stoppe l'envoi pour protéger le compte quand la limite du jour est atteinte")

        st.markdown("---")
        st.markdown('<div class="section-title">📋 Limites officielles Hostinger</div>',unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([
            {"Plan":"Gratuit / Essai","Messages/jour":"100","Destinataires/msg":"100","DKIM":"selon plan"},
            {"Plan":"Business Starter","Messages/jour":"1 000","Destinataires/msg":"100","DKIM":"✅"},
            {"Plan":"Business Premium","Messages/jour":"3 000","Destinataires/msg":"100","DKIM":"✅"},
        ]),use_container_width=True,hide_index=True)
        st.caption("« Messages/jour » = entrants **+** sortants, sur 24h glissantes. "
                   "1 email à 1 destinataire avec 2 CC = **3 messages**. "
                   "Taille max email sortant : 35 Mo (pièce jointe 25 Mo).")

        st.markdown("---")
        st.markdown('<div class="section-title">✅ Bonnes pratiques anti-blocage</div>',unsafe_allow_html=True)
        rules=[("✅","Reste sous la limite de ton plan (jauge ci-dessus)"),
               ("✅","Délai 120s+ entre emails (déjà configuré)"),
               ("✅","Réduis les CC pour économiser ton quota"),
               ("❌","Ne pas faire d'envoi massif d'un coup"),
               ("❌","Ne pas réduire le délai sous 60s")]
        for icon,rule in rules:
            color="#e3f6ec" if icon=="✅" else "#fbe7e5"; tc="#0f8a4f" if icon=="✅" else "#c8362f"
            H(f"""<div style="background:{color};color:{tc};border-radius:9px;
              padding:.5rem .9rem;margin:.3rem 0;font-size:.86rem;font-weight:500;">{icon} {rule}</div>""")
    with tab4:
        st.markdown('<div class="section-title">📥 Export des données</div>',unsafe_allow_html=True)
        log=load_log()
        c1,c2,c3=st.columns(3)
        with c1:
            st.download_button("📋 email_log.json",
                data=LOG_FILE.read_bytes() if LOG_FILE.exists() else b"{}",
                file_name="email_log.json",mime="application/json",use_container_width=True)
        with c2:
            sent_e=sorted([(k,v) for k,v in log.items() if v.get("status")=="sent"],
                          key=lambda x:x[1].get("timestamp",""))
            df_e=pd.DataFrame([{"N°":i,"Date":v.get("timestamp","")[:10],
                "Organisation":k.replace("PRUDENT_","").replace("UMF_","").replace("IFACE_","").replace("PRIORITY_",""),
                "Email":v.get("to",["?"])[0],"Statut":"Envoyé"} for i,(k,v) in enumerate(sent_e,1)])
            buf=io.BytesIO()
            with pd.ExcelWriter(buf,engine="openpyxl") as w: df_e.to_excel(w,index=False)
            st.download_button("📊 rapport.xlsx",data=buf.getvalue(),file_name="rapport_logiterre.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
        with c3:
            csv_buf=io.StringIO()
            df_e.to_csv(csv_buf,index=False)
            st.download_button("📄 rapport.csv",data=csv_buf.getvalue().encode("utf-8-sig"),
                file_name="rapport_logiterre.csv",mime="text/csv",use_container_width=True)
        st.markdown("---")
        st.markdown('<div class="section-title">🗑️ Nettoyage</div>',unsafe_allow_html=True)
        c1,c2=st.columns(2)
        with c1:
            if st.button("🗑️ Vider l'état live (ctrl/live)",use_container_width=True):
                for f in [CTRL_FILE,LIVE_FILE]:
                    if f.exists(): f.unlink()
                st.success("✅ État live réinitialisé")
        with c2:
            st.markdown(f"PDFs : **{len(list(PDF_DIR.glob('*.pdf')))}** fichiers dans `PDF_ACADEMIES/`")
