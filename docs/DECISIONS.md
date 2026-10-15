# Decisions

A short log of design decisions and why. Newest milestone first; each entry says what was decided,
why, and what it costs.

## M2 — Full coverage (in progress, from 2026-10-15)

### NHTSA: vehicles, car seats, tires, equipment

- **Source: NHTSA's recall flat file**, `FLAT_RCL_POST_2010.zip` (15 MB zipped, 311 MB of text,
  refreshed daily), laid out in `RCL.txt`. One tab-separated UTF-8 row per make, model, model
  year and component; a recall is its campaign number. No keys or paging: backfills and daily
  syncs download the file and keep campaigns received in the window (17 s, 290 MB peak).
- **Backfill from 2010, not 2015.** Cars stay on the road for decades and the file starts in
  2010: 15,309 campaigns, which become 40,193 products (37,192 vehicles grouped by make and model
  with their model years, 3,001 car seats, tires and equipment). The database grows by 73 MB to
  500 MB after compaction.
- **Vehicles are matched on make, model and year, never by similarity**, and aren't embedded.
  A query is a vehicle when it comes from a VIN, or names a recalled make plus one of its recalled
  models or a model year ("Honda generator" is not a vehicle). Variants count ("2019 Silverado"
  finds "SILVERADO 1500" and "2500HD", labelled as variants), exact names first.
- **A vehicle match is at most "Check your unit".** Recalls cover certain VINs, and NHTSA's public
  API can't say whether a VIN is included, so every vehicle match points to NHTSA's VIN search
  (`https://www.nhtsa.gov/recalls?nhtsaId=<campaign>`, checked in a browser: NHTSA's site
  refuses scripted requests). A model NHTSA has recalled in other years gives *All clear* for a
  year without recalls; a model it has never recalled gives *Couldn't identify*, since a name
  mismatch is likelier than a perfect record. Model years up to 2010 without matches get *Can't
  check yet*, and older-vehicle matches carry a note: recalls filed before 2010 aren't loaded.
- **"Do not drive" and "park outside" advisories lead the hazard text.**
- **Brand evidence ignores vehicle rows.** Counting them made "Honda" appear in thousands of
  products, so it stopped counting as a brand and the Honda EU2200i generator recall (CPSC 8513)
  went unmatched: a dangerous miss caught while labelling, now a smoke-set case. Smoke set:
  57/57 (still a tuning set, not an accuracy estimate).
- **VINs are decoded by NHTSA's vPIC** (free, no key), validated with the check digit first (a
  failed check is a warning: only North American VINs must have one), kept in memory for a day,
  and never written to the database unless the user saves the vehicle to their list.
- **NHTSA recalls are emailed too.** The CPSC-only rule came from openFDA's terms; NHTSA's data has
  no such restriction.

### Installable app and web push

- **Manifest and icons come from Next.js metadata routes** (`app/manifest.ts`, `app/icon.tsx`):
  the icons are rendered at build time from the logo's SVG, so no binary images live in the
  repo. The mark sits inside the maskable safe zone.
- **The service worker does two things only:** an offline page for navigations, and Web Push.
  It never caches recall data or API responses: a stale verdict is worse than none. It
  registers in production builds only; tests that mock the API block it (a controlling worker
  can take requests past Playwright's mocks).
- **Push is per device and opt-in** from the account page, for signed-in (not demo) users.
  iPhones need the app added to the Home Screen first (iOS 16.4+), which the toggle explains.
  Alerts follow the email rules (one per item, recall, and channel; no FDA), at most one
  notification per user per run; subscriptions the push service reports gone (404/410) are
  deleted. Sent with `pywebpush` and VAPID keys from the environment.

## M1 — Thin slice (2026-10-13 to 10-14)

### Recall data

- **Sources: CPSC and openFDA (food, drugs, devices), every recall reported since 2015-01-01.**
  25,856 recalls and 75,176 products: CPSC 3,710 recalls (one product each); FDA food 6,353 recalls
  / 23,198 products, drugs 3,824 / 14,637, devices 11,969 / 33,631. openFDA has one record per
  product and a recall is its `event_id`; FDA recall dates can precede 2015 because the window is
  on the enforcement report date.
- **Every field and quirk was checked against real responses first** (`tests/fixtures`, with the
  URL and fetch time of each in `manifest.json`):
  - CPSC has no paging, so backfills go a year at a time. A misspelled parameter is silently
    ignored and returns the whole database, so parameter names are checked against the
    documented list and oversized answers are rejected. Its `Model` field is always empty since
    2015; model numbers are extracted from the description.
  - openFDA pages with `search_after` (`skip` stops at 26,000). OR queries need the grouped form
    `field:("A" "B")`. A 404 means "no results".
- **CPSC's error placeholder is never stored.** When its database fails, CPSC answers HTTP 200
  with one fake record (`RecallID` 0, title "Error retrieving Recalls: The underlying provider
  failed on Open."). The first re-sync stored one before this was caught. It also seems to cache
  that answer per URL: `2020-01-01..2020-01-12` kept failing for hours while `..01-10` and
  `01-02..` worked, and single days worked. So a failed window is retried with its end moved a day
  later each time (a new URL; overlaps are harmless because upserts are idempotent), then split
  at a random point. If it still fails, the sync run is recorded as failed instead of storing
  junk. Real response saved as `tests/fixtures/cpsc/provider_error.json`.
- **Extraction coverage** (share of products with each field, measured on the full backfill):

  | Source | UPC | Model | Lot | Restricted to some units | Brand |
  |---|---|---|---|---|---|
  | CPSC | 7% | 48% | 4% | 34% | 100% |
  | FDA food | 41% | 6% | 35% | 94% | 14% |
  | FDA drugs | 20% | 2% | 71% | 90% | 43% |
  | FDA devices | 44% | 78% | 48% | 97% | 0% |

  "Restricted" means the recall covers only some lots, dates or serials, so an identifier match
  is *Check your unit*, not *Recalled*. A sentence that only says where a serial number is
  printed no longer counts as a restriction (CPSC 10853, Cuisinart CGG-6331, covers every unit).
  FDA brands come from openFDA's `brand_name` or the label's "Distributed by"/"Manufactured for"
  company ("Distributed by: EzriCare, LLC").
- **A full backfill takes about 2.5 minutes of fetching** (CPSC's per-year requests are the slow
  part) with peak memory around 310 MB.
- **Changed products keep their embedding** unless the embedded text (name, brand, category)
  changed. A re-sync after an extraction fix then costs seconds instead of a 26-minute re-embed.

### Storage (Neon free plan: 1 GB per project)

- Neon's free plan is **1 GB per project** (neon.com/pricing, checked 2026-10-13); M0 planned for
  0.5 GB, the older limit.
- Measured on the full backfill with every product embedded, after `VACUUM FULL`: **427 MB**
  (products 370 MB, of which the HNSW index is 83 MB; recalls 48 MB). Straight after embedding it
  was 489 MB, because every embedding is an UPDATE that leaves a dead row, so production is seeded
  by restoring a dump rather than embedding in place. That leaves over half the plan for M4's
  passages and for growth.
- Compaction that paid off: no duplicate of the product name in raw FDA records, raw `code_info`
  capped at 2,000 characters (the full text is still parsed), at most 300 codes per product, and
  a trigram index on the first 200 characters of names only.

### Embeddings and vector search

- **`BAAI/bge-small-en-v1.5` through fastembed (ONNX), not sentence-transformers.** Same model,
  no PyTorch: the API image is 1.14 GB with the model baked in and idles at 191 MiB of memory.
- **Embedding all 75,176 products took 25.6 minutes on an M-series Mac** (49 products/s, batch
  512, peak 2.2 GB). Daily syncs add a few hundred products at most.
- **HNSW on `halfvec(384)`, `m=16, ef_construction=64`, queried with `ef_search=400`.** Against
  exact search on 80 queries (60 real product names, 20 typed descriptions): recall@50 0.988, and
  0.995 for neighbours with cosine ≥ 0.70 (the only ones the matcher uses), at 1.9 ms median.
  At `ef_search=100` recall@50 was 0.926 and one query got 0.20; at 200 it was 0.970. The higher
  setting costs nothing noticeable at this size.
- **Binary-quantised HNSW was rejected:** a 25 MB index instead of 83 MB, but recall@50 was only
  0.846 even when re-ranking 400 candidates.

### Matching (baseline, rules only)

- **Candidates** come from four retrievers merged with reciprocal-rank fusion: exact identifiers
  (UPC, model, weak table codes), full-text search, trigram similarity on name prefixes, and
  vector search.
- **Tiers follow the approved rules.** *Recalled* needs a UPC match, or a model number plus the
  brand, on a recall without unresolved unit restrictions. Everything weaker is *Check your unit*.
- **Brand evidence must be rare.** A word counts as the brand only if few recalled products
  mention it (≤ 500; ≤ 100 when it is just the first word of a product name). "Graco" is in 3
  products, "Multi" in over 1,000. Compound names match ("Ninja" in "SharkNinja").
- **Same brand isn't enough for a "family" match.** When the query and the recall both name a
  product line beyond the brand and the lines differ ("Rock 'n Play" vs "Infant Motion Seats"),
  only a near-identical name (cosine ≥ 0.88) still matches. The recall headline's product phrase
  counts as part of the recall's line ("IKEA Recalls 29 Million MALM ... Dressers").
- **A model the user gave that the recall doesn't list argues against a match** ("Peloton PL01"
  is not the "Bike+ PL02" recall). Listed series count ("WA50B" covers "WA50B5100AW"), and so do
  codes in the product name ("PR70P Clip-In Pedals").
- **Name-only matches don't decide verdicts for categories we don't cover yet.** A car seat
  matched by name to a CPSC rocking seat stays *Can't check yet*; only an identifier match would
  count.
- **Thresholds are hand-set** (cosine 0.80 for a family match, 0.76 for safety-critical
  categories, 0.88 when product lines differ) and replaced by calibrated ones in M3.
- **The M1 smoke set is a tuning set, not an accuracy claim.** `data/labels/m1_smoke.jsonl` has 53
  hand-labelled real inputs (recalled, check-unit, hard negatives, out-of-scope, vague) plus
  recalls that must *not* be listed. The first run scored 44/53; fixes guided by it bring it to
  53/53, with 35 ms median latency locally. Because the rules were tuned on it, that score says
  nothing about unseen products; M3's labelled test set will.

### Accounts, privacy, and alerts

- **Better Auth's tables are created by Alembic**, with snake_case columns mapped field by field
  in `apps/web/src/lib/auth.ts`, so one migration system owns the schema.
- **Magic links are stored hashed** and expire in 15 minutes; **session IP tracking is off.**
- **"Try the demo" signs you in to a private anonymous account** (Better Auth's anonymous plugin)
  with six real examples covering every verdict. Signing in with an email moves the list to the
  real account. Demo accounts never get email and are deleted after 7 days by the daily job.
- **Signed-in calls go through the Next.js server**, which signs a 2-minute HS256 token for the
  API. The browser never holds it, and the API only trusts it for a user that still exists.
- **Anonymous checks call the API directly** and are rate limited per IP in memory (20/minute,
  300/day). The free API is a single instance, so in-process counters are exact.
- **Checks are not stored.** An event records the input type, verdict, match count and latency,
  never the product. "Try it now" hands its text to `/check` in session storage, so it never
  appears in URLs or server logs.
- **Barcode names come from Open Food Facts, looked up by our server** (users' IPs aren't
  shared) and cached for 30 days (3 days when not found), within its 15 reads/minute limit.
- **Email alerts are CPSC-only** (approved). openFDA's terms say its data must not be used to
  alert the public, so FDA matches appear on the list and are recorded as skipped alerts.
- **One alert per item, recall and channel,** enforced by a unique constraint. Matches found when
  an item is saved aren't emailed (the user just saw them). Each run sends at most one email per
  user. M1 re-checks every watched item after each sync (0.5 s for 6 items here). M3 replaces
  this with a reverse lookup from new recalls and benchmarks it.
- **Mail goes out over SMTP**: Mailpit locally, Resend's SMTP in production. One code path for
  both apps.

### Hosting

- **The API runs on an Oracle Cloud Always Free VM (decided 2026-10-14), not Hugging Face.**
  Hugging Face's docs now say "Gradio and Docker Spaces run on compute and require a paid plan to
  create: PRO for personal accounts" (forum reports date the change to mid-2026). Of the
  alternatives, Render's free tier has 0.1 CPU and sleeps after 15 idle minutes (about a minute
  to wake), and Cloud Run needs a billing account. Oracle's Always Free Ampere A1 shapes are
  always on with ARM cores and gigabytes of RAM; its sign-up verifies a card. The image already
  builds and runs on ARM64 (Apple Silicon builds are ARM64).
- **The VM deploys itself by pulling.** A systemd timer checks `main` every 10 minutes and deploys
  the newest commit whose CI run passed, running migrations first; GitHub holds no SSH key.
  Caddy terminates HTTPS (automatic certificates) and keeps no access log. The API trusts
  `X-Forwarded-For` only from the compose network (`FORWARDED_ALLOW_IPS`), so a client can't
  spoof its address past the rate limit; tested locally on the production compose file.

### Web

- **Barcode scanning uses the browser's BarcodeDetector where it exists, otherwise ZXing
  (WebAssembly).** The 1 MB `.wasm` is copied from `node_modules` at build time and served from
  our own origin, not a CDN. A WebKit Playwright project covers iPhones, which take the ZXing
  path.
- **Cache Components patterns:** session reads sit behind `<Suspense>`; the landing page's recall
  counter is a cached component, so its "updated X ago" is computed when the cache refreshes (a
  few minutes at most).
- **Links are read, never fetched.** Hyphenated slugs are scanned for model numbers that the
  hyphens split ("…-Gas-Grill-CGG-6331").

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
- **The product brief stays private.** The spec this project is built from isn't published;
  code comments that cite "SPEC §x" refer to it.
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
- ~~**WebKit in Playwright.**~~ Added in M1 (iPhone 15 emulation).
