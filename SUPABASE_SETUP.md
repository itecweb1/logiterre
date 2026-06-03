# 🟢 Activer le tracking RSVP en ligne (Supabase — gratuit)

Objectif : les confirmations de participation (RSVP) sont enregistrées dans une base
**persistante** accessible par ton app Streamlit Cloud — **sans ton Mac**.

---

## Étape 1 — Créer un projet Supabase (gratuit)
1. Va sur **supabase.com** → **Start your project** → connecte-toi (GitHub possible)
2. **New project** → nom `logiterre` → choisis une région (Europe) → mot de passe DB (note-le) → **Create**
3. Attends ~1 min que le projet démarre

## Étape 2 — Créer les tables
1. Dans Supabase → menu gauche **SQL Editor** → **New query**
2. Colle ceci puis clique **Run** :
```sql
create table if not exists rsvp (
  id bigint generated always as identity primary key,
  org_name text, email text, response text,
  delegates int default 1, speaker int default 0, notes text,
  created timestamptz default now()
);
create table if not exists opens (
  id bigint generated always as identity primary key,
  email text, org_name text, created timestamptz default now()
);
```
→ "Success. No rows returned" = c'est bon ✅

## Étape 3 — Récupérer tes clés
1. Supabase → ⚙️ **Project Settings** → **API**
2. Copie **Project URL** (ex: `https://abcd.supabase.co`)
3. Copie la clé **`service_role`** (section *Project API keys* — clique "reveal")
   ⚠️ Cette clé est secrète — elle ne va QUE dans les Secrets Streamlit (jamais dans le code)

## Étape 4 — Ajouter aux Secrets Streamlit
1. **share.streamlit.io** → ton app `logiterre` → ⚙️ **Settings → Secrets**
2. Ajoute (en plus de ce qui y est déjà) :
```toml
SUPABASE_URL = "https://abcd.supabase.co"
SUPABASE_KEY = "ta-cle-service_role"
APP_URL      = "https://logiterre.streamlit.app"
```
3. **Save** → l'app redémarre toute seule

## Étape 5 — C'est actif 🎉
- Les emails contiennent un bouton **"Confirm your participation"** qui pointe vers
  `https://logiterre.streamlit.app/?rsvp=...`
- Le destinataire clique → remplit le formulaire → **enregistré dans Supabase**
- Tu vois tout dans **✅ Inscriptions RSVP** (badge 🟢 "Données : Supabase")
  → persiste même après redémarrage, **sans ton Mac**

---

## ℹ️ Ce qui marche / ne marche pas en cloud
| Fonction | Cloud (Supabase) |
|---|---|
| ✅ RSVP (qui confirme) | **OUI** — via le lien, persistant |
| ✅ Délégués / intervenants | **OUI** |
| 👁️ Pixel d'ouverture invisible | Non (nécessite un service image séparé — phase 2) |

> Le RSVP capture l'essentiel : **qui vient vraiment**. Le pixel d'ouverture
> (invisible) reste possible plus tard via une fonction Supabase Edge si besoin.
