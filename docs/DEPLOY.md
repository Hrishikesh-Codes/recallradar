# Deploying RecallRadar (free tiers)

Four services, all on free plans, plus GitHub Actions. Do them in this order; each step lists the
values the next one needs. Secrets go only into each service's settings, never into the repo.

| Piece | Service | Free plan limits that matter |
|---|---|---|
| Database | Neon | 1 GB per project, 100 CU-hours/month, scales to zero after 5 minutes |
| API | **To decide** (see below) | Hugging Face Docker Spaces now need a paid PRO plan |
| Web | Vercel (Hobby) | Non-commercial use |
| Email | Resend | 3,000 emails/month, 100/day; needs a verified domain |
| Schedule | GitHub Actions | Free for public repos |

## 1. Database (Neon)

1. Create a project (Postgres 17, the version CI and Docker use) in a US region.
2. Copy two connection strings from *Connect*: the **direct** one (for migrations and seeding)
   and the **pooled** one (`-pooler` in the host, for the web app and API).
3. Seed it from a local database that already has the backfill and embeddings
   (`make sync MODE=backfill && make embed`), about 25 seconds:

   ```bash
   scripts/seed-database.sh postgresql://recallradar:recallradar@localhost:5432/recallradar "<neon direct URL>"
   ```

   It migrates the schema, copies the recall tables, builds the vector index once, and prints the
   counts and database size (433 MB measured for the full 2015+ data).

## 2. Email (Resend)

1. Add and verify the sending domain (DNS records for SPF and DKIM at your DNS provider).
2. Create an API key with sending access only.
3. SMTP URL for both apps: `smtps://resend:<API key>@smtp.resend.com:465`.
4. Pick the sender addresses, e.g. `RecallRadar <alerts@your-domain>` and
   `RecallRadar <sign-in@your-domain>`.

## 3. API

> **Host to be decided.** Hugging Face's Spaces docs now say "Gradio and Docker Spaces run on
> compute and require a paid plan to create: PRO for personal accounts" (checked 2026-10-14);
> only static Spaces stay free. The steps below are for a Space on a PRO account; the API image
> runs anywhere that runs Docker (512 MB of RAM is enough: it idles at 191 MiB).

1. Create a Space: SDK **Docker**, hardware **CPU basic**, public.
2. In the Space's *Settings → Variables and secrets*, add:

   | Name | Kind | Value |
   |---|---|---|
   | `DATABASE_URL` | secret | Neon **pooled** URL |
   | `API_TOKEN_SECRET` | secret | `openssl rand -hex 32` (the web app gets the same value) |
   | `CORS_ORIGINS` | variable | the web app's URL, e.g. `https://recallradar.vercel.app` |
   | `ENVIRONMENT` | variable | `production` |
   | `SENTRY_DSN` | secret | optional |

3. In GitHub (*Settings → Secrets and variables → Actions*): secret `HF_TOKEN` (a Hugging Face
   token with write access to the Space) and variable `HF_SPACE` (`user/space-name`). Then run
   **Deploy API to Hugging Face Spaces** from the Actions tab. Later pushes that touch the API
   deploy automatically.
4. Check `https://<user>-<space-name>.hf.space/readyz` returns `{"status":"ok","database":true}`.

## 4. Web (Vercel)

1. Import the GitHub repo. **Root directory: `apps/web`** (Next.js is detected).
2. Environment variables (Production):

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | the Space URL, `https://<user>-<space-name>.hf.space` |
   | `DATABASE_URL` | Neon **pooled** URL |
   | `BETTER_AUTH_URL` | the site's URL |
   | `BETTER_AUTH_SECRET` | `openssl rand -base64 32` |
   | `API_TOKEN_SECRET` | same value as the Space's |
   | `SMTP_URL` | the Resend SMTP URL |
   | `MAIL_FROM` | the sign-in sender |

3. Deploy, then set the Space's `CORS_ORIGINS` to the final URL if it changed.

## 5. Daily sync and alerts (GitHub Actions)

In the repo's Actions settings:

| Name | Kind | Value |
|---|---|---|
| `DATABASE_URL` | secret | Neon **direct** URL |
| `SMTP_URL` | secret | the Resend SMTP URL |
| `OPENFDA_API_KEY` | secret | optional; raises openFDA's limit to 120,000 requests/day |
| `SENTRY_DSN` | secret | optional |
| `MAIL_FROM` | variable | the alerts sender |
| `WEB_URL` | variable | the site's URL (for links in emails) |
| `API_URL` | variable | the Space URL (the run also wakes it up) |

Run **Sync recalls and send alerts** once by hand to check it; after that it runs daily at 09:17
UTC. A failed source fails the run (and GitHub emails the repo owner), but the other sources'
data and alerts still go through.

## Checks after deploying

- The landing page shows "Tracking N recalls" (not the fallback text).
- `/check`: "Peloton bike PL01" → Recalled; "Hydro Flask 32 oz water bottle" → All clear;
  "2019 Honda Civic" → Can't check yet.
- "Try the demo" opens a list of six items; signing in with an email moves it to your account.
- `/account` → Download my data, then Delete everything.
