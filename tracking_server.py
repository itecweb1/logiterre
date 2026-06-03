#!/usr/bin/env python3
"""LOGITERRE 2026 — Serveur de tracking (pixel d'ouverture + désinscription)

Lance : python3 tracking_server.py [port]
Routes :
  GET /pixel/<contact_id>.png   → marque l'email ouvert, renvoie un pixel 1x1
  GET /u/<contact_id>           → page de désinscription
  GET /health                   → ok

Pour un usage RÉEL (recipients externes), expose ce serveur publiquement :
  - ngrok http 8765
  - ou déploie sur Railway / Render / un VPS
"""
import sys, base64, sqlite3
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = Path(__file__).resolve().parent / "logiterre.db"

# Pixel PNG transparent 1x1
PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

UNSUB_PAGE = """<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Désinscription — LOGITERRE 2026</title>
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:linear-gradient(135deg,#0f0c29,#302b63);
  display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
.card{{background:#fff;border-radius:18px;padding:3rem 2.5rem;max-width:480px;text-align:center;
  box-shadow:0 20px 60px rgba(0,0,0,.4);}}
h1{{color:#1a1a2e;font-size:1.5rem;}}
p{{color:#555;line-height:1.6;}}
.ok{{color:#238636;font-size:3rem;}}
.brand{{color:#888;font-size:.8rem;margin-top:1.5rem;}}
</style></head><body><div class="card">
<div class="ok">✓</div>
<h1>{title}</h1>
<p>{msg}</p>
<div class="brand">LOGITERRE 2026 — sg@logiterre-expo.com</div>
</div></body></html>"""

REGISTER_FORM = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Registration — LOGITERRE 2026</title>
<style>
*{{box-sizing:border-box;}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);
  margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:1rem;}}
.card{{background:#fff;border-radius:20px;padding:2.5rem;max-width:560px;width:100%;
  box-shadow:0 24px 70px rgba(0,0,0,.45);}}
.logo{{text-align:center;font-size:2.5rem;}}
h1{{color:#1a1a2e;font-size:1.5rem;text-align:center;margin:.3rem 0;}}
.sub{{color:#888;text-align:center;font-size:.9rem;margin-bottom:1.5rem;}}
.org{{background:#f0f4ff;border-radius:10px;padding:.8rem 1rem;text-align:center;font-weight:600;
  color:#302b63;margin-bottom:1.5rem;}}
label{{display:block;font-weight:600;color:#333;margin:1rem 0 .3rem;font-size:.9rem;}}
input,textarea,select{{width:100%;padding:.7rem;border:1.5px solid #e2e8f0;border-radius:10px;
  font-size:.95rem;font-family:inherit;}}
.radios{{display:flex;gap:.6rem;margin-top:.4rem;}}
.radios label{{flex:1;text-align:center;padding:.8rem;border:2px solid #e2e8f0;border-radius:12px;
  cursor:pointer;margin:0;transition:all .15s;}}
.radios input{{display:none;}}
.radios input:checked+span{{font-weight:700;}}
.r-yes:has(input:checked){{border-color:#238636;background:#e8f5e9;}}
.r-maybe:has(input:checked){{border-color:#d29922;background:#fff8e1;}}
.r-no:has(input:checked){{border-color:#da3633;background:#fdecea;}}
.btn{{width:100%;margin-top:1.5rem;padding:1rem;background:linear-gradient(135deg,#302b63,#7c5cbf);
  color:#fff;border:none;border-radius:12px;font-size:1rem;font-weight:700;cursor:pointer;}}
.brand{{text-align:center;color:#aaa;font-size:.78rem;margin-top:1.5rem;}}
</style></head><body><div class="card">
<div class="logo">🌍</div>
<h1>LOGITERRE 2026</h1>
<div class="sub">International Transport &amp; Logistics Forum · Casablanca · 20–22 Oct 2026</div>
<div class="org">{org}</div>
<form method="POST" action="/register/{cid}">
  <label>Will your institution attend?</label>
  <div class="radios">
    <label class="r-yes"><input type="radio" name="response" value="yes" required><span>✅ Yes</span></label>
    <label class="r-maybe"><input type="radio" name="response" value="maybe"><span>🤔 Maybe</span></label>
    <label class="r-no"><input type="radio" name="response" value="no"><span>❌ No</span></label>
  </div>
  <label>Number of delegates</label>
  <input type="number" name="delegates" value="1" min="0" max="50">
  <label><input type="checkbox" name="speaker" value="1" style="width:auto;margin-right:.5rem;">We would like to propose a speaker / panelist</label>
  <label>Message (optional)</label>
  <textarea name="notes" rows="3" placeholder="Any questions or special requests..."></textarea>
  <button class="btn" type="submit">Confirm registration</button>
</form>
<div class="brand">LOGITERRE 2026 — sg@logiterre-expo.com — +212 673 642 4246</div>
</div></body></html>"""


def db_exec(query, params=()):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB error] {e}")
        return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # silence

    def do_GET(self):
        path = self.path.split("?")[0]

        # ── Pixel d'ouverture ─────────────────────────────────
        if path.startswith("/pixel/"):
            token = path[len("/pixel/"):].replace(".png", "")
            if token.isdigit():
                db_exec("UPDATE contacts SET opened_at=datetime('now') "
                        "WHERE id=? AND opened_at IS NULL", (int(token),))
                db_exec("INSERT INTO email_events (contact_id, event_type) VALUES (?, 'opened')",
                        (int(token),))
                print(f"[OPEN] contact #{token}")
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PIXEL)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(PIXEL)
            return

        # ── Désinscription ────────────────────────────────────
        if path.startswith("/u/"):
            token = path[len("/u/"):]
            if token.isdigit():
                conn = sqlite3.connect(DB_PATH, timeout=10)
                r = conn.execute("SELECT email FROM contacts WHERE id=?", (int(token),)).fetchone()
                conn.close()
                if r:
                    email = r[0]
                    db_exec("INSERT OR REPLACE INTO unsubscribes (email, reason) VALUES (?, 'link')", (email,))
                    db_exec("UPDATE contacts SET unsubscribed=1, status='unsubscribed' "
                            "WHERE LOWER(email)=LOWER(?)", (email,))
                    print(f"[UNSUB] {email}")
                    html = UNSUB_PAGE.format(
                        title="Désinscription confirmée",
                        msg=f"L'adresse <b>{email}</b> ne recevra plus d'emails de LOGITERRE 2026. "
                            "Nous respectons votre choix.")
                else:
                    html = UNSUB_PAGE.format(title="Lien invalide", msg="Ce lien n'est plus valide.")
            else:
                html = UNSUB_PAGE.format(title="Lien invalide", msg="Ce lien n'est plus valide.")
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # ── Page d'inscription (formulaire) ───────────────────
        if path.startswith("/register/"):
            token = path[len("/register/"):]
            org = "Your Institution"
            if token.isdigit():
                conn = sqlite3.connect(DB_PATH, timeout=10)
                r = conn.execute("SELECT name FROM contacts WHERE id=?", (int(token),)).fetchone()
                conn.close()
                if r and r[0]: org = r[0]
            html = REGISTER_FORM.format(org=org, cid=token)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # ── Health ────────────────────────────────────────────
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        from urllib.parse import parse_qs
        path = self.path.split("?")[0]
        if path.startswith("/register/"):
            token = path[len("/register/"):]
            length = int(self.headers.get("Content-Length", 0))
            data = parse_qs(self.rfile.read(length).decode("utf-8")) if length else {}
            response  = data.get("response", ["maybe"])[0]
            delegates = data.get("delegates", ["1"])[0]
            speaker   = 1 if data.get("speaker") else 0
            notes     = data.get("notes", [""])[0]
            try: delegates = int(delegates)
            except: delegates = 1

            cid = int(token) if token.isdigit() else None
            org = ""; email = ""
            if cid:
                conn = sqlite3.connect(DB_PATH, timeout=10)
                r = conn.execute("SELECT name,email FROM contacts WHERE id=?", (cid,)).fetchone()
                conn.close()
                if r: org, email = r[0], r[1]

            # Sauvegarde RSVP
            db_exec("""INSERT INTO rsvp (contact_id,org_name,email,response,delegates,speaker,notes)
                       VALUES (?,?,?,?,?,?,?)""",
                    (cid, org, email, response, delegates, speaker, notes))
            if cid:
                db_exec("UPDATE contacts SET replied_at=datetime('now') WHERE id=?", (cid,))
            print(f"[RSVP] {org or token}: {response} ({delegates} délégués)")

            msg = {"yes": f"Merci ! La participation de <b>{org}</b> est confirmée. "
                          "Nous reviendrons vers vous avec les détails logistiques.",
                   "maybe": f"Merci pour votre réponse. Nous gardons une place pour <b>{org}</b> "
                            "et restons à votre disposition pour toute question.",
                   "no": f"Merci de nous avoir informés. L'invitation reste ouverte pour "
                         "une prochaine édition."}.get(response, "Merci pour votre réponse !")
            html = UNSUB_PAGE.format(title="Réponse enregistrée ✓", msg=msg)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"🛰️  Tracking server actif sur http://localhost:{port}")
    print(f"   Pixel : http://localhost:{port}/pixel/<id>.png")
    print(f"   Unsub : http://localhost:{port}/u/<id>")
    print(f"   (Pour recipients externes : ngrok http {port})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
        server.shutdown()


if __name__ == "__main__":
    main()
