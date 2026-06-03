"""LOGITERRE 2026 — SQLite Database Layer"""
import sqlite3, json, time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "logiterre.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            subject  TEXT,
            template TEXT DEFAULT 'default',
            created  TEXT DEFAULT (datetime('now')),
            status   TEXT DEFAULT 'draft'
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER REFERENCES campaigns(id),
            name        TEXT NOT NULL,
            email       TEXT NOT NULL,
            org_type    TEXT DEFAULT 'general',
            score       INTEGER DEFAULT 5,
            status      TEXT DEFAULT 'pending',
            sent_at     TEXT,
            opened_at   TEXT,
            replied_at  TEXT,
            bounced     INTEGER DEFAULT 0,
            followup_sent INTEGER DEFAULT 0,
            unsubscribed  INTEGER DEFAULT 0,
            notes       TEXT,
            UNIQUE(campaign_id, email)
        );

        CREATE TABLE IF NOT EXISTS email_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id  INTEGER REFERENCES contacts(id),
            event_type  TEXT,
            event_time  TEXT DEFAULT (datetime('now')),
            details     TEXT
        );

        CREATE TABLE IF NOT EXISTS templates (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT UNIQUE NOT NULL,
            subject TEXT,
            body    TEXT,
            type    TEXT DEFAULT 'general'
        );

        CREATE TABLE IF NOT EXISTS followup_queue (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id  INTEGER REFERENCES contacts(id),
            send_after  TEXT,
            sent        INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS unsubscribes (
            email      TEXT PRIMARY KEY,
            added_at   TEXT DEFAULT (datetime('now')),
            reason     TEXT
        );

        CREATE TABLE IF NOT EXISTS rsvp (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id  INTEGER,
            org_name    TEXT,
            email       TEXT,
            response    TEXT,              -- yes / maybe / no
            delegates   INTEGER DEFAULT 1,
            speaker     INTEGER DEFAULT 0, -- souhaite intervenir
            notes       TEXT,
            created     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reply_triage (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT,
            subject     TEXT,
            category    TEXT,
            handled     INTEGER DEFAULT 0,
            created     TEXT DEFAULT (datetime('now')),
            UNIQUE(email, subject)
        );
        """)
        # Insert default templates if empty
        row = c.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        if row == 0:
            _insert_default_templates(c)

def _insert_default_templates(c):
    templates = [
        ("Académique", "Official Invitation – LOGITERRE 2026 International Forum", "academic",
         """Dear Professor / Dear Research Director,

On behalf of the LOGITERRE 2026 Organizing Committee, it is my great honor to invite your esteemed academic institution to participate in the Third Edition of the International LOGITERRE Forum & Exhibition (Casablanca, Morocco, 20–22 October 2026).

This premier academic and research event, organized under the High Patronage of His Majesty King Mohammed VI, will gather leading researchers, professors, and PhD students to present cutting-edge work in transport, logistics, supply chain, and sustainable mobility.

We specifically invite your institution to participate through:
  • Keynote presentations and research papers
  • Academic poster sessions
  • Panel discussions and roundtables
  • Joint research collaboration workshops

Please find attached our official invitation letter and academic program.

With highest academic regards,
LOGITERRE 2026 Organizing Committee
sg@logiterre-expo.com | +212 673 642 4246"""),

        ("Industrie", "Official Invitation – LOGITERRE 2026 Business Forum", "industry",
         """Dear Sir / Madam,

On behalf of the LOGITERRE 2026 Organizing Committee, we are delighted to extend this official invitation to your esteemed organization to participate in the Third Edition of the International LOGITERRE Forum & Exhibition.

LOGITERRE 2026 (Casablanca, Morocco, 20–22 October 2026) is the premier platform connecting industry leaders, transport operators, logistics providers, port authorities, and technology innovators across Africa, Europe, and the Middle East.

As a key industry player, your participation would bring unparalleled value through:
  • Business matchmaking sessions
  • Exhibition space and product showcases
  • Partnership and investment forums
  • B2B networking with 500+ decision-makers

Please find attached our official invitation and business program.

With highest professional regards,
LOGITERRE 2026 Organizing Committee
sg@logiterre-expo.com | +212 673 642 4246"""),

        ("Gouvernement", "Official Invitation – LOGITERRE 2026 High-Level Ministerial Forum", "government",
         """Your Excellency / Dear Minister / Dear Director General,

On behalf of the LOGITERRE 2026 Organizing Committee, it is my distinct honor to extend this official invitation to your esteemed institution to participate in the Third Edition of the International LOGITERRE Forum & Exhibition.

Organized under the High Patronage of His Majesty King Mohammed VI, LOGITERRE 2026 (Casablanca, 20–22 October 2026) will convene Ministers of Transport, Directors General, and senior policymakers to advance strategic frameworks for sustainable transport, connectivity, and logistics development across Africa and the global economy.

Your high-level participation would contribute to:
  • Ministerial roundtables and policy dialogues
  • Regional infrastructure and connectivity frameworks
  • Bilateral cooperation agreements
  • Public-private partnership initiatives

Please find attached our official invitation letter and ministerial program.

With the highest consideration and respect,
LOGITERRE 2026 Organizing Committee
sg@logiterre-expo.com | +212 673 642 4246"""),

        ("Fédération", "Official Invitation – LOGITERRE 2026 International Forum & Exhibition", "federation",
         """Dear Secretary General / Dear President,

On behalf of the LOGITERRE 2026 Organizing Committee, it is my great honor to invite your esteemed federation and its member organizations to participate in the Third Edition of the International LOGITERRE Forum & Exhibition (Casablanca, Morocco, 20–22 October 2026).

LOGITERRE 2026 represents a unique opportunity for freight forwarding, logistics, and transport associations worldwide to:
  • Network with 500+ industry professionals
  • Present federation activities and advocacy positions
  • Explore cross-border cooperation frameworks
  • Access African market development opportunities

We warmly invite your federation to mobilize member companies for collective participation.

With highest association regards,
LOGITERRE 2026 Organizing Committee
sg@logiterre-expo.com | +212 673 642 4246"""),

        ("Follow-up", "Following Up: LOGITERRE 2026 – Your Participation", "followup",
         """Dear Sir / Madam,

I hope this message finds you well.

I am writing to kindly follow up on our previous invitation sent to your esteemed organization regarding the Third Edition of the International LOGITERRE Forum & Exhibition (Casablanca, Morocco, 20–22 October 2026).

We understand that schedules are busy, and we wanted to ensure our invitation reached the right person within your organization. We would be truly honored to count your institution among our distinguished participants.

If you have any questions or require additional information, please do not hesitate to reach out directly.

Registration deadline: September 30, 2026
Website: https://linktr.ee/LOGITERRE.PRO

We sincerely hope to welcome you in Casablanca.

Warm regards,
LOGITERRE 2026 Organizing Committee
sg@logiterre-expo.com | +212 673 642 4246"""),
    ]
    for name, subject, ttype, body in templates:
        c.execute("INSERT OR IGNORE INTO templates (name, subject, body, type) VALUES (?,?,?,?)",
                  (name, subject, body, ttype))


# ── Campaign CRUD ─────────────────────────────────────────────
def create_campaign(name, subject="", template="default"):
    with get_conn() as c:
        cur = c.execute("INSERT INTO campaigns (name,subject,template) VALUES (?,?,?)",
                        (name, subject, template))
        return cur.lastrowid

def get_campaigns():
    with get_conn() as c:
        return [dict(r) for r in c.execute(
            """SELECT c.*,
               COUNT(DISTINCT ct.id) as total,
               SUM(CASE WHEN ct.status='sent' THEN 1 ELSE 0 END) as sent,
               SUM(CASE WHEN ct.opened_at IS NOT NULL THEN 1 ELSE 0 END) as opened,
               SUM(CASE WHEN ct.replied_at IS NOT NULL THEN 1 ELSE 0 END) as replied,
               SUM(CASE WHEN ct.bounced=1 THEN 1 ELSE 0 END) as bounced,
               SUM(CASE WHEN ct.status='pending' THEN 1 ELSE 0 END) as pending
               FROM campaigns c LEFT JOIN contacts ct ON c.id=ct.campaign_id
               GROUP BY c.id ORDER BY c.created DESC""").fetchall()]

def get_campaign(cid):
    with get_conn() as c:
        r = c.execute("SELECT * FROM campaigns WHERE id=?", (cid,)).fetchone()
        return dict(r) if r else None

def delete_campaign(cid):
    with get_conn() as c:
        c.execute("DELETE FROM contacts WHERE campaign_id=?", (cid,))
        c.execute("DELETE FROM campaigns WHERE id=?", (cid,))


# ── Contacts CRUD ─────────────────────────────────────────────
def add_contacts(campaign_id, contacts):
    """contacts: list of dicts with name, email, org_type, score"""
    with get_conn() as c:
        for ct in contacts:
            c.execute("""INSERT OR IGNORE INTO contacts
                         (campaign_id, name, email, org_type, score)
                         VALUES (?,?,?,?,?)""",
                      (campaign_id, ct.get("name",""), ct.get("email",""),
                       ct.get("org_type","general"), ct.get("score",5)))

def get_contacts(campaign_id, status=None):
    with get_conn() as c:
        if status:
            rows = c.execute("SELECT * FROM contacts WHERE campaign_id=? AND status=? ORDER BY score DESC",
                             (campaign_id, status)).fetchall()
        else:
            rows = c.execute("SELECT * FROM contacts WHERE campaign_id=? ORDER BY score DESC",
                             (campaign_id,)).fetchall()
        return [dict(r) for r in rows]

def ensure_contact(campaign_id, name, email, org_type=None, score=None):
    """Insère le contact s'il n'existe pas, retourne son id."""
    with get_conn() as c:
        r = c.execute("SELECT id FROM contacts WHERE campaign_id=? AND LOWER(email)=LOWER(?)",
                      (campaign_id, email)).fetchone()
        if r:
            return r["id"]
        cur = c.execute("""INSERT INTO contacts (campaign_id,name,email,org_type,score)
                           VALUES (?,?,?,?,?)""",
                        (campaign_id, name, email,
                         org_type or detect_org_type(name, email),
                         score or auto_score(name, email)))
        return cur.lastrowid

def find_contact_by_email(email):
    with get_conn() as c:
        r = c.execute("SELECT * FROM contacts WHERE LOWER(email)=LOWER(?) ORDER BY id DESC LIMIT 1",
                      (email,)).fetchone()
        return dict(r) if r else None

def get_default_campaign():
    """Retourne (ou crée) la campagne 'Envois directs' pour les envois sans campagne explicite."""
    with get_conn() as c:
        r = c.execute("SELECT id FROM campaigns WHERE name='Envois directs'").fetchone()
        if r:
            return r["id"]
    return create_campaign("Envois directs", "", "default")

def get_opens(campaign_id=None):
    """Liste des contacts qui ont ouvert."""
    with get_conn() as c:
        if campaign_id:
            rows = c.execute("""SELECT * FROM contacts WHERE campaign_id=? AND opened_at IS NOT NULL
                                ORDER BY opened_at DESC""", (campaign_id,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM contacts WHERE opened_at IS NOT NULL ORDER BY opened_at DESC").fetchall()
        return [dict(r) for r in rows]

def mark_sent(contact_id, email):
    with get_conn() as c:
        c.execute("UPDATE contacts SET status='sent', sent_at=datetime('now') WHERE id=?", (contact_id,))
        c.execute("INSERT INTO email_events (contact_id, event_type) VALUES (?, 'sent')", (contact_id,))

def mark_opened(contact_id):
    with get_conn() as c:
        c.execute("UPDATE contacts SET opened_at=datetime('now') WHERE id=? AND opened_at IS NULL", (contact_id,))
        c.execute("INSERT INTO email_events (contact_id, event_type) VALUES (?, 'opened')", (contact_id,))

def mark_bounced(email):
    with get_conn() as c:
        c.execute("UPDATE contacts SET bounced=1, status='bounced' WHERE LOWER(email)=LOWER(?)", (email,))

def mark_replied(email):
    with get_conn() as c:
        c.execute("UPDATE contacts SET replied_at=datetime('now') WHERE LOWER(email)=LOWER(?)", (email,))

def mark_unsubscribe(email, reason=""):
    with get_conn() as c:
        c.execute("INSERT OR REPLACE INTO unsubscribes (email, reason) VALUES (?,?)", (email.lower(), reason))
        c.execute("UPDATE contacts SET unsubscribed=1, status='unsubscribed' WHERE LOWER(email)=LOWER(?)", (email,))

def get_unsubscribes():
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM unsubscribes ORDER BY added_at DESC").fetchall()]

def is_unsubscribed(email):
    with get_conn() as c:
        r = c.execute("SELECT 1 FROM unsubscribes WHERE email=?", (email.lower(),)).fetchone()
        return r is not None


# ── Templates ─────────────────────────────────────────────────
def get_templates():
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM templates ORDER BY name").fetchall()]

def get_template(name):
    with get_conn() as c:
        r = c.execute("SELECT * FROM templates WHERE name=?", (name,)).fetchone()
        return dict(r) if r else None

def save_template(name, subject, body, ttype="general"):
    with get_conn() as c:
        c.execute("INSERT OR REPLACE INTO templates (name,subject,body,type) VALUES (?,?,?,?)",
                  (name, subject, body, ttype))

# Mapping type d'organisation → type de template
ORGTYPE_TO_TEMPLATE = {
    "academic":      "academic",
    "research":      "academic",
    "government":    "government",
    "international": "government",   # UN/OCDE = haut niveau institutionnel
    "federation":    "federation",
    "port":          "industry",
    "logistics":     "industry",
    "industry":      "industry",
    "general":       None,           # garde le template par défaut de l'utilisateur
}

_TEMPLATE_CACHE = {}
def template_for_orgtype(org_type):
    """Retourne (subject, body) du template adapté au type d'org, ou None."""
    ttype = ORGTYPE_TO_TEMPLATE.get(org_type)
    if not ttype:
        return None
    if ttype in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[ttype]
    with get_conn() as c:
        r = c.execute("SELECT subject, body FROM templates WHERE type=? LIMIT 1", (ttype,)).fetchone()
        result = (r["subject"], r["body"]) if r else None
        _TEMPLATE_CACHE[ttype] = result
        return result


# ── Follow-up ─────────────────────────────────────────────────
def schedule_followup(contact_id, days=7):
    with get_conn() as c:
        send_after = time.strftime("%Y-%m-%d", time.localtime(time.time() + days*86400))
        c.execute("INSERT OR REPLACE INTO followup_queue (contact_id, send_after) VALUES (?,?)",
                  (contact_id, send_after))

def get_pending_followups():
    today = time.strftime("%Y-%m-%d")
    with get_conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT fq.*, ct.name, ct.email, ct.campaign_id
            FROM followup_queue fq JOIN contacts ct ON fq.contact_id=ct.id
            WHERE fq.sent=0 AND fq.send_after<=? AND ct.status='sent'
            AND ct.replied_at IS NULL AND ct.unsubscribed=0
            ORDER BY fq.send_after""", (today,)).fetchall()]

def mark_followup_sent(fq_id):
    with get_conn() as c:
        c.execute("UPDATE followup_queue SET sent=1 WHERE id=?", (fq_id,))
        c.execute("UPDATE contacts SET followup_sent=1 WHERE id=("
                  "SELECT contact_id FROM followup_queue WHERE id=?)", (fq_id,))


# ── Analytics ─────────────────────────────────────────────────
def get_campaign_stats(campaign_id):
    with get_conn() as c:
        r = c.execute("""SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) as sent,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='bounced' THEN 1 ELSE 0 END) as bounced,
            SUM(CASE WHEN status='unsubscribed' THEN 1 ELSE 0 END) as unsub,
            SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) as opened,
            SUM(CASE WHEN replied_at IS NOT NULL THEN 1 ELSE 0 END) as replied,
            SUM(CASE WHEN followup_sent=1 THEN 1 ELSE 0 END) as followups
            FROM contacts WHERE campaign_id=?""", (campaign_id,)).fetchone()
        return dict(r) if r else {}

def get_timeline(campaign_id):
    with get_conn() as c:
        rows = c.execute("""SELECT DATE(ee.event_time) as day, ee.event_type, COUNT(*) as cnt
            FROM email_events ee JOIN contacts ct ON ee.contact_id=ct.id
            WHERE ct.campaign_id=? GROUP BY day, event_type ORDER BY day""",
            (campaign_id,)).fetchall()
        return [dict(r) for r in rows]


# ── Scoring ───────────────────────────────────────────────────
ORG_SCORES = {
    "academic":    9, "government": 9, "international": 10,
    "federation":  8, "port":       8, "industry":       7,
    "logistics":   8, "research":   9, "general":        5,
}

def auto_score(name, email):
    n = name.lower(); e = email.lower()
    for kw, score in [
        (["un.org","oecd","wto","imo.org","iata","worldbank","unctad","unesco","undp",
          "africa-union","afdb","isdb","weforum"], 10),
        (["ministry","ministre","gouvernement","government","gov.","authority","mawani"], 9),
        (["university","université","universidad","polytechnic","institute","school of",
          "college","hbs.edu","mit.edu",".edu",".ac."], 9),
        (["port","harbor","harbour","terminal","shipping","maritime"], 8),
        (["federation","association","union","council","chamber","fiata","ichca"], 8),
        (["logistics","transport","freight","cargo","supply","forwarding"], 7),
    ]:
        if any(k in n or k in e for k in kw): return score
    return 5


# ── Contact type detection ────────────────────────────────────
def detect_org_type(name, email):
    n = name.lower(); e = email.lower()
    if any(k in n or k in e for k in ["un.org","oecd","wto","imo.org","iata","worldbank","imf","unicef","undp","unctad","africa-union","afdb","isdb","weforum","unesco"]): return "international"
    if any(k in n or k in e for k in ["university","université","universidad","polytechnic","school of","institute of","college","academic","research","hbs.edu",".edu",".ac."]): return "academic"
    if any(k in n or k in e for k in ["ministry","minister","gouvernement","government","gov.","official","authority","prefecture","mawani"]): return "government"
    if any(k in n or k in e for k in ["federation","association","union","council","chamber","syndicate","fiata","ichca","cscmp"]): return "federation"
    if any(k in n or k in e for k in ["port","harbor","terminal","shipping","maritime","naval"]): return "port"
    if any(k in n or k in e for k in ["logistics","freight","cargo","forwarding","customs","transport","transit"]): return "logistics"
    return "industry"


# ── RSVP ──────────────────────────────────────────────────────
def save_rsvp(contact_id, org_name, email, response, delegates=1, speaker=0, notes=""):
    with get_conn() as c:
        c.execute("""INSERT INTO rsvp (contact_id,org_name,email,response,delegates,speaker,notes)
                     VALUES (?,?,?,?,?,?,?)""",
                  (contact_id, org_name, email, response, delegates, speaker, notes))
        # marque le contact comme "répondu"
        if contact_id:
            c.execute("UPDATE contacts SET replied_at=datetime('now') WHERE id=?", (contact_id,))

def get_rsvps():
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM rsvp ORDER BY created DESC").fetchall()]

def get_rsvp_stats():
    with get_conn() as c:
        r = c.execute("""SELECT
            COUNT(*) as total,
            SUM(CASE WHEN response='yes' THEN 1 ELSE 0 END) as yes,
            SUM(CASE WHEN response='maybe' THEN 1 ELSE 0 END) as maybe,
            SUM(CASE WHEN response='no' THEN 1 ELSE 0 END) as no,
            SUM(CASE WHEN response='yes' THEN delegates ELSE 0 END) as total_delegates,
            SUM(CASE WHEN speaker=1 THEN 1 ELSE 0 END) as speakers
            FROM rsvp""").fetchone()
        return dict(r) if r else {}

def get_contact_for_rsvp(contact_id):
    with get_conn() as c:
        r = c.execute("SELECT id,name,email FROM contacts WHERE id=?", (contact_id,)).fetchone()
        return dict(r) if r else None

# ── Reply triage storage ──────────────────────────────────────
def save_triage(email, subject, category):
    with get_conn() as c:
        c.execute("INSERT OR IGNORE INTO reply_triage (email,subject,category) VALUES (?,?,?)",
                  (email, subject, category))

def mark_triage_handled(email, subject):
    with get_conn() as c:
        c.execute("UPDATE reply_triage SET handled=1 WHERE email=? AND subject=?", (email, subject))

def is_triage_handled(email, subject):
    with get_conn() as c:
        r = c.execute("SELECT handled FROM reply_triage WHERE email=? AND subject=?",
                      (email, subject)).fetchone()
        return bool(r["handled"]) if r else False

# Init on import
init_db()
