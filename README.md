# RecallRadar

Check whether something you own has been recalled. Scan a barcode, paste a product link,
describe it, or enter a VIN, and get a clear, evidence-backed verdict from official U.S. recall
notices (CPSC, FDA, USDA FSIS, NHTSA). RecallRadar then keeps watching your list and alerts you
if a recall is announced later.

> **Status: Milestone 1 built (deployment pending); Milestone 2 in progress.** Checks against
> 42,304 recalls from CPSC, FDA and USDA FSIS (since 2015) and NHTSA (vehicles, car seats, tires,
> since 2010) work end to end locally: type, paste a link, scan a barcode, photograph a label, or
> enter a VIN, and get a verdict with its evidence; save items to a list; get an email or push
> notification when a CPSC, NHTSA or FSIS recall matches one later. FSIS blocks automated
> downloads, so meat recalls are imported from a browser-saved copy for now. Numbers below are
> measured; how is in [docs/DECISIONS.md](docs/DECISIONS.md).

## How a check works

1. **Read the input.** Typed text is parsed for brand, model numbers, barcodes, lot codes and a
   purchase date. Links are read from the URL text only; we never open store pages or ask for
   store passwords. Barcodes are validated, and for food we look up the name on Open Food Facts.
2. **Find candidates** among 117,247 recalled products with four retrievers merged by
   reciprocal-rank fusion: exact identifiers, full-text search, trigram similarity, and embeddings
   (`bge-small-en-v1.5`, HNSW on `halfvec`).
3. **Decide the tier with plain rules that never overclaim.** *Recalled* only for a barcode, or a
   model number plus the brand, on a recall that covers every unit. *Check your unit* when the
   recall covers only some lots, dates or serials, or when the same brand's product line matches.
   *All clear* says "no recalls found in the sources we checked", never "safe". *Can't check yet*
   for categories other agencies cover.
4. **Show the evidence:** why it matched, what to check on your label and where to find it, the
   hazard, what to do, and the official notice.

## Measured so far

| What | Result |
|---|---|
| Recalls indexed | 42,304: CPSC 3,710 · FDA food 6,353 · drugs 3,824 · devices 11,969 · USDA FSIS 1,139 (since 2015) · NHTSA 15,309 (since 2010) |
| Database size, everything embedded | 368 MB recalls + 161 MB vectors, in two Neon projects (free databases are capped at 512 MiB each) |
| Vector search vs exact search | recall@50 0.988 at 1.9 ms median (80 queries) |
| Check latency (local, M-series Mac) | 32 ms median over the 60-case smoke set, vectors in a separate database |
| Smoke set | 60/60 after tuning on it: a regression check, **not** an accuracy estimate (M3) |

## What's here

- **Web** (`apps/web`): Next.js 16, React 19, TypeScript (strict), Tailwind CSS 4. Landing page
  with a WebGL2 radar and a live recall counter, the check flow (text, link, camera barcode
  scanning), the verdict screen, sign-in by email link, a demo account, My List, account
  settings with export and delete, and a privacy page. Tested for WCAG AA, keyboard use, reduced
  motion, Android and iPhone layouts.
- **API** (`apps/api`): FastAPI on Python 3.12. `/v1/check`, feedback, recall details, coverage
  stats, and the signed-in list endpoints; per-IP rate limits; the embedding model baked into
  the Docker image. Its OpenAPI schema generates the web app's TypeScript types.
- **Ingest** (`packages/ingest`): CPSC and openFDA clients and the extraction of barcodes, model
  numbers, lot codes, sale dates and unit restrictions from recall text.
- **Matching** (`packages/matching`): retrieval, tier rules, and re-checks of watched items.
- **Jobs** (`jobs`): daily sync, embedding, and alerts (GitHub Actions cron); the evaluation CLI.
- **CI**: lint, strict type checks, Python tests against real Postgres with real recall fixtures
  and the real model, web unit tests, a production build, Playwright E2E with axe scans on four
  device profiles, a Docker image smoke test, and a secret scan on every push.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the system diagram and data model,
[docs/DEPLOY.md](docs/DEPLOY.md) for deploying on free tiers,
[docs/DESIGN.md](docs/DESIGN.md) for the design system, and
[docs/DECISIONS.md](docs/DECISIONS.md) for why things are the way they are.

## Run it locally

You need [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/) and Node 24+, and Docker
(Docker Desktop, OrbStack, or Colima).

```bash
make install              # Python + web dependencies
make up                   # Postgres, Mailpit, and the API (migrations run on start)
make sync MODE=backfill   # every recall since 2015 (about 3 minutes)
make embed                # embeddings for semantic search (about 25 minutes the first time)
make web                  # http://localhost:3000
```

The API is at http://localhost:8000 (`/healthz`, `/readyz`, `/docs`), and Mailpit's inbox (for
sign-in links and alerts) at http://localhost:8025. Sign-in and My List need the same
`API_TOKEN_SECRET` in `.env` and `apps/web/.env.local` (any random 32+ characters).

| Command | What it does |
|---|---|
| `make check` | Lint, strict type checks, and all unit tests |
| `make e2e` | Production build + Playwright (desktop, mobile, reduced motion) |
| `make sync` / `make embed` / `make alerts` | The daily job's steps, by hand |
| `make eval` | Run the labelled smoke set through the matcher |
| `make migrate` | Apply migrations to `DATABASE_URL` |
| `make openapi` | Regenerate the API schema and TypeScript types |
| `make help` | Everything else |

Copy `.env.example` to `.env` (and `apps/web/.env.example` to `apps/web/.env.local`) to override
defaults. Never commit real secrets.

## Repository layout

```
apps/web            Next.js PWA
apps/api            FastAPI service (+ Dockerfile)
deploy/oracle       production compose + Caddy + cloud-init for the API's VM
packages/core       settings, logging, models, migrations
packages/ingest     CPSC + openFDA ingesters, extraction
packages/identify   inputs -> ProductQuery (text, link, barcode; photos and VIN in M2)
packages/matching   retrieval, tier rules, watched-item re-checks (trained scorer in M3)
packages/ask        citation-grounded RAG                    (M4)
packages/earlywarn  complaint-surge backtest                 (M5)
jobs                daily sync -> embed -> alerts, evaluation CLI
data/labels         hand-labelled evaluation data
docs                architecture, decisions, design, evaluations
```

## Roadmap

| Milestone | Scope |
|---|---|
| **M0 — Foundation** ✅ | Monorepo, Docker Compose, migrations, CI, design system, docs |
| **M1 — Thin slice** (built; deploying) | CPSC + FDA ingestion on a schedule; typed/link/barcode input; baseline matcher with tiers; verdict screen; radar landing; magic-link sign-in, My List, email alerts; live demo |
| M2 — Full coverage | USDA FSIS + NHTSA + VIN; label photo and order screenshot input; web push; installable PWA |
| M3 — Matching v2 | Labelled test set, trained and calibrated scorer, benchmark, EVAL.md |
| M4 — Ask | RAG with citations, verification, abstention, and an ablation study |
| M5 — Early warning | Do complaint surges predict recalls? A strictly out-of-time backtest |
| M6 — Launch | Load test, admin health page, demo video, launch |

## Disclaimer

RecallRadar is an independent project, not affiliated with CPSC, FDA, USDA, or NHTSA. Always
confirm with the official recall notice. "No recall found" never means a product is safe.
