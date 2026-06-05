// LOGITERRE 2026 — Tracking de clic + redirection (Supabase Edge Function)
// Enregistre le clic dans la table `clicks` PUIS redirige (HTTP 302) vers la destination.
// C'est la méthode pro (façon Mailchimp) : 100% cloud, fiable, sans Mac.
// URL : https://<projet>.supabase.co/functions/v1/click?email=...&org=...&to=linktr

// Anti open-redirect : on ne redirige QUE vers des destinations connues/sûres.
const SAFE: Record<string, string> = {
  linktr: "https://linktr.ee/LOGITERRE",
};
const DEFAULT_URL = "https://linktr.ee/LOGITERRE";

function resolveDest(req: URL): string {
  const to = req.searchParams.get("to") ?? "";
  if (to && SAFE[to]) return SAFE[to];
  // url= accepté uniquement s'il pointe vers linktr.ee (sinon destination par défaut)
  const url = req.searchParams.get("url") ?? "";
  try {
    if (url) {
      const u = new URL(url);
      if (u.protocol === "https:" && u.hostname.endsWith("linktr.ee")) return u.toString();
    }
  } catch (_e) { /* ignore */ }
  return DEFAULT_URL;
}

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const email = url.searchParams.get("email") ?? "";
  const org = url.searchParams.get("org") ?? "";
  const dest = resolveDest(url);

  if (email) {
    try {
      const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
      const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
      if (SUPABASE_URL && KEY) {
        await fetch(`${SUPABASE_URL}/rest/v1/clicks`, {
          method: "POST",
          headers: {
            "apikey": KEY,
            "Authorization": `Bearer ${KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email, org_name: org, kind: "linktr" }),
        });
      }
    } catch (_e) { /* ne bloque jamais la redirection */ }
  }

  return new Response(null, {
    status: 302,
    headers: {
      "Location": dest,
      "Cache-Control": "no-store, no-cache, must-revalidate",
    },
  });
});
