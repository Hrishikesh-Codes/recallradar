/**
 * This site's public address, for absolute URLs (share images, sitemap, canonical links). Set by
 * BETTER_AUTH_URL in production; on Vercel without it, the project's production domain.
 */
export const SITE_URL = (
  process.env.BETTER_AUTH_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : "http://localhost:3000")
).replace(/\/$/, "");

export const SITE_DESCRIPTION =
  "Check whether something you own has been recalled. Scan a barcode, paste a link, describe it, or enter a VIN, and see the evidence from official U.S. recall notices.";
