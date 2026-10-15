"use client";

import { useEffect } from "react";

/** Registers /sw.js in production builds (in development it would fight hot reloading). */
export function ServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => {
      // Offline page and push just stay unavailable; the site works without them.
    });
  }, []);
  return null;
}
