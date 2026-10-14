import { cacheLife } from "next/cache";

import { API_URL, type Stats } from "@/lib/api/client";

/**
 * Recall counts and freshness for the landing counter and the checking screen. Cached for a few
 * minutes; null when the API is asleep or unreachable, so pages still render without it.
 */
export async function getStats(): Promise<Stats | null> {
  "use cache";
  cacheLife("minutes");
  try {
    const response = await fetch(`${API_URL}/v1/stats`, { signal: AbortSignal.timeout(5000) });
    return response.ok ? ((await response.json()) as Stats) : null;
  } catch {
    return null;
  }
}
