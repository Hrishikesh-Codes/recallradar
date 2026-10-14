import "server-only";

import { Pool } from "pg";

/**
 * Postgres for Better Auth (and the anonymous -> real account hand-over). Everything else goes
 * through the API. Neon's pooled URL works here; a few connections are plenty per instance.
 */
const globalForPool = globalThis as unknown as { recallradarPool?: Pool };

export const pool =
  globalForPool.recallradarPool ??
  new Pool({
    connectionString:
      process.env.DATABASE_URL ?? "postgresql://recallradar:recallradar@localhost:5432/recallradar",
    max: 3,
  });

if (process.env.NODE_ENV !== "production") globalForPool.recallradarPool = pool;
