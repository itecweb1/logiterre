// LOGITERRE 2026 — Pixel de tracking d'ouverture (Supabase Edge Function)
// Sert un pixel 1x1 transparent ET enregistre l'ouverture dans la table `opens`.
// URL publique : https://<projet>.supabase.co/functions/v1/pixel?email=...&org=...
import { createClient } from "jsr:@supabase/supabase-js@2";

// PNG transparent 1x1
const PIXEL = Uint8Array.from(
  atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="),
  (c) => c.charCodeAt(0),
);

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const email = url.searchParams.get("email") ?? "";
  const org = url.searchParams.get("org") ?? "";

  // Enregistre l'ouverture (best-effort, ne bloque jamais le pixel)
  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );
    if (email) {
      await supabase.from("opens").insert({ email, org_name: org });
    }
  } catch (_e) { /* ignore */ }

  return new Response(PIXEL, {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "no-store, no-cache, must-revalidate",
      "Access-Control-Allow-Origin": "*",
    },
  });
});
