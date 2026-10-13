# Decisions

A short log of design decisions and why. Newest milestone first; each entry says what was decided,
why, and what it costs.

## M0 — Foundation (2026-10-13)

### Approved changes to the spec

- **Auth: Better Auth instead of Auth.js.** Auth.js has been maintained by the Better Auth team
  since September 2025, and they recommend Better Auth for new projects. Magic links via its
  plugin, sessions in Postgres. Lands in M1.
- **Next.js talks to FastAPI as a backend-for-frontend.** The browser calls Next.js route
  handlers; they call FastAPI with a short-lived signed token naming the user. FastAPI never
  handles cookies. Vercel Hobby functions run up to 300s, enough to wait out an API cold start.
- **Radar effect: one raw WebGL2 fragment shader, not Three.js / React Three Fiber.** A halftone
  dot grid, rings and a sweep are all per-pixel maths on a single full-screen quad, at a fraction
  of the bundle size, which matters for the LCP < 2.5s budget. Static fallback for reduced motion
  and no-WebGL. Lands in M1.
- **"Try the demo" button** instead of a seeded account behind a magic link (a stranger can't
  receive the demo inbox's email). Lands in M1.
- **Tier rules that never overclaim.**
  - *Recalled* only when an identifier (UPC, or model number + brand) matches **and** the recall
    has no lot/date/serial restriction we haven't resolved. Otherwise *Check your unit*.
  - Coverage guard: if a product's category belongs to a source we don't ingest yet (car seats
    and vehicles are NHTSA's, meat/poultry/eggs are FSIS's), the answer is *Can't check yet*,
    never *All clear*. The design system already has this fifth state.
- **`packages/core`** (not in the spec's layout) holds the settings, logging, SQLAlchemy models
  and migrations shared by the API, the jobs and every package.

### Repository and tooling

- **uv workspace for Python, pnpm for the one web app, a Makefile on top.** Turborepo/Nx would
  add little with a single JS app. `make help` lists everything.
- **Python 3.12, ruff, mypy `--strict`, pytest.** TypeScript strict plus
  `noUncheckedIndexedAccess`, ESLint, Prettier, Vitest, Playwright.
- **Next.js 16 with Cache Components and typed routes.** Typed routes make a link to a page that
  doesn't exist a type error. TypeScript stays on 5.9, which `create-next-app` pins: TypeScript 7
  has no JavaScript compiler API yet (per the bundled Next.js docs).
- **The API contract is generated, not hand-written.** FastAPI's OpenAPI schema is committed and
  `openapi-typescript` generates the web app's types; CI fails if either is stale.
- **Local Docker via Colima.** It only affects local development: Vercel, Hugging Face Spaces and
  Neon run the deployed app. Postgres image `pgvector/pgvector:pg17` (pgvector 0.8.7); match
  Neon's Postgres major version when the project is created.
- **Project lives outside iCloud.** The Desktop was iCloud-synced; iCloud marks everything inside
  dot-folders (like `.venv`) hidden, and Python 3.12 skips hidden `.pth` files, so workspace
  packages stopped importing. The repo moved to `~/Developer/recallradar`, and `make install`
  clears the flag on macOS in case it happens elsewhere.

### Database

- **Alembic migrations are the production schema;** they ship inside `recallradar_core` so jobs
  and tests can run them from code. A test fails if the models and the migrations ever differ.
- **Closed vocabularies are text + `CHECK` constraints,** not native Postgres `ENUM` types, which
  need awkward migrations to change.
- **Embeddings: 384-dim `halfvec`** (`BAAI/bge-small-en-v1.5`), 2 bytes per dimension instead of
  4, because Neon's free plan is 0.5 GB. Vector indexes are created in M1, once there's real data
  to size them against.
- **Synchronous SQLAlchemy + psycopg 3.** FastAPI runs sync endpoints in a thread pool; at a few
  hundred users that's plenty, and the jobs are batch work. `pool_pre_ping` because Neon suspends
  idle computes, which drops pooled connections.
- **Freshness is measurable from day one:** `recall.first_seen_at` (our ingest time) against the
  source's publication date, and `sync_run` records every ingester run.
- **Tests never touch `DATABASE_URL`.** They create throwaway databases on `TEST_DATABASE_URL`
  (default: the local compose database). Locally, DB tests skip if Postgres is down; CI sets
  `REQUIRE_DB_TESTS=1` so they fail instead.

### Design system

- **Fonts: Host Grotesk (display) and Inter (text),** chosen from a side-by-side against the
  reference's licensed faces. Host Grotesk matches MSCHN's proportions closest (width-to-cap-height
  of "CAUSE THE": 6.47 vs 6.5); Archivo and Sora were about 12% wider. The reference's strokes are
  lighter, so the display weight is 450, not 500. Inter is closer to Suisse Int'l than Geist.
  Details in DESIGN.md.
- **Button hover matches the reference** (a deep-orange fill wiping up from the bottom, with a
  two-arrow slide) rather than the spec's "subtle warm fill". The reference keeps sand text on
  that fill, which is 3.39:1 and fails WCAG AA, so our label turns near-black (5.14:1).
- **Input borders use `muted-2`, not `muted-3`.** `muted-3` on the page is 2.998:1, just under the
  3:1 WCAG 1.4.11 needs for control boundaries. A unit test caught it; it had looked like 3.00.
- **Reduced motion turns transitions off entirely** (`transition: none`), not the common
  "0.01ms" trick. That trick makes every element transition every property, including inherited
  `visibility`, which hid the menu for one frame and broke moving focus into it. Found by the
  reduced-motion Playwright run.

### Scheduled jobs (GitHub Actions cron): known limitations

- Scheduled runs can start late, and some can be dropped, when GitHub Actions is busy (GitHub's
  docs call out the top of every hour). Schedules avoid minute 0, and the freshness metric will
  include whatever delay remains.
- GitHub disables scheduled workflows in public repos after 60 days without repository activity;
  they have to be re-enabled from the Actions tab.
- Actions minutes are free for public repos, which is one reason the repo is public.

### Deferred

- **`httpx` → `httpx2`.** Starlette now warns that its test client wants `httpx2`. Adding that new
  dependency was blocked by the permission check, so the tests keep `httpx` for now (a deprecation
  warning, nothing broken). Swap when approved.
- **WebKit in Playwright.** M0 runs Chromium only (desktop, Pixel 7 emulation, reduced motion). Add
  a WebKit project in M1, since barcode scanning on iPhone depends on Safari behaviour.
