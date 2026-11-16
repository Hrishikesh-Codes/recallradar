import type { NextConfig } from "next";

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").origin;

/*
 * Security headers for production builds. The CSP allows only our own origin plus the API:
 * - 'unsafe-inline' scripts: Next's inline bootstrap needs it without per-request nonces, and
 *   nonces would make every page dynamic (the landing page is static). Scripts can still only
 *   load from this origin.
 * - 'wasm-unsafe-eval' and blob: workers: the barcode reader (ZXing) and label OCR (Tesseract),
 *   both served from this origin.
 * - img https: — official notice photos come from agency sites (cpsc.gov).
 */
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src 'self' data: blob: ${API_ORIGIN}`,
  "worker-src 'self' blob:",
  "media-src 'self' blob:",
  "manifest-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const SECURITY_HEADERS = [
  { key: "Content-Security-Policy", value: CSP },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // The camera is for scanning barcodes and photographing labels; nothing else is used.
  { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=(), payment=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
];

const nextConfig: NextConfig = {
  async headers() {
    // Development needs eval and websockets for hot reload; the policy is for real builds.
    if (process.env.NODE_ENV !== "production") return [];
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  cacheComponents: true,
  partialPrefetching: true,
  // Links to routes that don't exist fail type-checking.
  typedRoutes: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
