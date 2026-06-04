// LOGITERRE 2026 — Pixel de tracking d'ouverture (Supabase Edge Function)
// Sert un pixel 1x1 transparent ET enregistre l'ouverture dans la table `opens`.
// Version sans dépendance (fetch direct vers PostgREST) — fiable au démarrage à froid.
// URL : https://<projet>.supabase.co/functions/v1/pixel?email=...&org=...

const PIXEL = Uint8Array.from(
  atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="),
  (c) => c.charCodeAt(0),
);

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const email = url.searchParams.get("email") ?? "";
  const org = url.searchParams.get("org") ?? "";

  if (email) {
    try {
      const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
      const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
      if (SUPABASE_URL && KEY) {
        await fetch(`${SUPABASE_URL}/rest/v1/opens`, {
          method: "POST",
          headers: {
            "apikey": KEY,
            "Authorization": `Bearer ${KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email, org_name: org }),
        });
      }
    } catch (_e) { /* ne bloque jamais le pixel */ }
  }

  return new Response(PIXEL, {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "no-store, no-cache, must-revalidate",
      "Access-Control-Allow-Origin": "*",
    },
  });
});
