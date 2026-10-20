# Deploying RecallRadar (free tiers)

Four services, all on free plans, plus GitHub Actions. Do them in this order; each step lists the
values the next one needs. Secrets go only into each service's settings, never into the repo.

| Piece | Service | Free plan limits that matter |
|---|---|---|
| Database | Neon (two projects) | 512 MiB per database (branch), 100 CU-hours/month per project, scales to zero after 5 minutes |
| API | Oracle Cloud Always Free (Ampere A1 VM) | 4 ARM cores and 24 GB in total; always on. Sign-up verifies a card; Always Free resources aren't charged |
| Web | Vercel (Hobby) | Non-commercial use |
| Email | Resend | 3,000 emails/month, 100/day; needs a verified domain |
| Schedule | GitHub Actions | Free for public repos |

## 1. Database (Neon)

Neon's free plan caps each database branch at 512 MiB (the "1 GB per project" on its pricing
page is the project total), and the full dataset is about 530 MB. So there are two projects:
recalls in one (368 MB measured), product embeddings with their vector index in the other
(161 MB). See DECISIONS.md, "Storage".

1. Create two projects in the same US region (recalls on Postgres 17, the version CI and Docker
   use; 18 works for the vectors project, which holds one table), e.g.
   `recallradar` and `recallradar-vectors`.
2. From each project's *Connect*, copy the **direct** connection string (for jobs, migrations,
   and seeding) and the **pooled** one (`-pooler` in the host, for the web app and API).
3. Add the direct strings as repository secrets: `DATABASE_URL` and `VECTOR_DATABASE_URL`.
4. Seed both from GitHub: *Actions → Seed production database → Run workflow*, typing
   `replace recall data`. It backfills and embeds everything on the runner (about 90 minutes,
   mostly embedding), then copies compact rows into Neon and builds the vector index once. It
   refuses to run if production has user accounts. The same script works from a machine that
   can reach Neon on port 5432:

   ```bash
   scripts/seed-database.sh --replace postgresql://recallradar:recallradar@localhost:5432/recallradar "<recalls direct URL>" "<vectors direct URL>"
   ```

5. USDA FSIS blocks scripted downloads, so meat recalls aren't in the seed. Import them from a
   machine that can reach Neon, with a copy of FSIS's API response saved from a browser:

   ```bash
   DATABASE_URL="<recalls direct URL>" uv run recallradar-sync --source fsis --mode backfill --file fsis.json
   DATABASE_URL="<recalls direct URL>" VECTOR_DATABASE_URL="<vectors direct URL>" uv run recallradar-embed
   ```

## 2. Email (Resend)

1. Add and verify the sending domain (DNS records for SPF and DKIM at your DNS provider).
2. Create an API key with sending access only.
3. SMTP URL for both apps: `smtps://resend:<API key>@smtp.resend.com:465`.
4. Pick the sender addresses, e.g. `RecallRadar <alerts@your-domain>` and
   `RecallRadar <sign-in@your-domain>`.

## 3. API (Oracle Cloud Always Free VM)

The API runs in Docker behind Caddy, which gets and renews the HTTPS certificate. The VM deploys
itself: every 10 minutes it checks `main` and deploys the newest commit whose CI run passed
(`deploy/oracle/update.sh`), running migrations first. GitHub holds no SSH keys.

1. **Create the instance** (*Compute → Instances → Create*), in a region near your Neon database
   (e.g. US East (Ashburn) with Neon's `us-east-1`):
   - Image: **Canonical Ubuntu 24.04**. Shape: **VM.Standard.A1.Flex** (Always Free); 2 OCPUs and
     12 GB is plenty (it idles at about 200 MB).
   - Networking: a public subnet with a **public IPv4 address**.
   - SSH keys: upload your public key.
   - *Advanced options → Management → Initialization script*: paste
     [`deploy/oracle/cloud-init.yaml`](../deploy/oracle/cloud-init.yaml). It installs Docker,
     opens ports 80/443 in the instance firewall, checks out the repo, and starts the timer.
2. **Open ports 80 and 443 in the VCN**: *Networking → Virtual cloud networks → (your VCN) →
   Security → (default security list) → Add ingress rules*: source `0.0.0.0/0`, TCP, destination
   ports `80,443` (and UDP 443 for HTTP/3, optional).
3. **Pick the API's name.** Either add an `A` record for a subdomain you own (e.g.
   `recallradar-api.example.com`) pointing at the VM's public IP, or use
   `<IP with dashes>.sslip.io` (e.g. `203-0-113-7.sslip.io`), which needs no DNS.
4. **Fill in the secrets** on the VM (`ssh ubuntu@<ip>`), replacing every `CHANGE_ME`:

   ```bash
   sudo nano /opt/recallradar/.env
   ```

   | Name | Value |
   |---|---|
   | `API_DOMAIN` | the name from step 3 |
   | `DATABASE_URL` | the recalls project's **pooled** URL |
   | `VECTOR_DATABASE_URL` | the vectors project's **pooled** URL |
   | `API_TOKEN_SECRET` | `openssl rand -hex 32` (the web app gets the same value) |
   | `CORS_ORIGINS` | the web app's URL, e.g. `https://recallradar.vercel.app` |
   | `SENTRY_DSN` | optional |

5. **Deploy now** instead of waiting for the timer, and watch it:

   ```bash
   sudo systemctl start recallradar-update.service && journalctl -u recallradar-update -f
   ```

   The first build takes a few minutes (it downloads the embedding model into the image).
6. Check `https://<API_DOMAIN>/readyz` returns `{"status":"ok","database":true}`.

Useful later: `docker compose -f /opt/recallradar/src/deploy/oracle/compose.yaml logs -f api`;
the deployed commit is in `/opt/recallradar/deployed`.

## 4. Web (Vercel)

1. Import the GitHub repo. **Root directory: `apps/web`** (Next.js is detected).
2. Environment variables (Production):

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://<API_DOMAIN>` |
   | `DATABASE_URL` | the recalls project's **pooled** URL (accounts live there too) |
   | `BETTER_AUTH_URL` | the site's URL |
   | `BETTER_AUTH_SECRET` | `openssl rand -base64 32` |
   | `API_TOKEN_SECRET` | same value as the VM's |
   | `SMTP_URL` | the Resend SMTP URL |
   | `MAIL_FROM` | the sign-in sender |

3. Deploy, then update `CORS_ORIGINS` in the VM's `.env` if the final URL differs, and restart:
   `docker compose -f /opt/recallradar/src/deploy/oracle/compose.yaml up -d`.

## 5. Daily sync and alerts (GitHub Actions)

In the repo's Actions settings:

| Name | Kind | Value |
|---|---|---|
| `DATABASE_URL` | secret | the recalls project's **direct** URL |
| `VECTOR_DATABASE_URL` | secret | the vectors project's **direct** URL |
| `SMTP_URL` | secret | the Resend SMTP URL |
| `OPENFDA_API_KEY` | secret | optional; raises openFDA's limit to 120,000 requests/day |
| `SENTRY_DSN` | secret | optional |
| `MAIL_FROM` | variable | the alerts sender |
| `WEB_URL` | variable | the site's URL (for links in emails) |

Run **Sync recalls and send alerts** once by hand to check it; after that it runs daily at 09:17
UTC. A failed source fails the run (and GitHub emails the repo owner), but the other sources'
data and alerts still go through.

## Checks after deploying

- The landing page shows "Tracking N recalls" (not the fallback text).
- `/check`: "Peloton bike PL01" → Recalled; "Hydro Flask 32 oz water bottle" → All clear;
  "2019 Honda Civic" → Can't check yet.
- "Try the demo" opens a list of six items; signing in with an email moves it to your account.
- `/account` → Download my data, then Delete everything.
