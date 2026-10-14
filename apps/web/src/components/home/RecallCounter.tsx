import { cacheLife } from "next/cache";

import { getStats } from "@/lib/api/stats";
import { formatCount, listSources, timeAgo } from "@/lib/format";

/**
 * "Tracking 25,856 recalls from CPSC and FDA · updated 2 hours ago", from the live API. Cached
 * with the stats, so "ago" is measured when the cache refreshes (minutes at most).
 */
export async function RecallCounter() {
  "use cache";
  cacheLife("minutes");
  const stats = await getStats();
  if (!stats) return <p className="chip text-muted-1">Official U.S. recall notices</p>;
  return (
    <p className="chip text-muted-1">
      <span aria-hidden className="size-1.5 rounded-full bg-accent" />
      Tracking {formatCount(stats.recalls)} recalls from{" "}
      {listSources(stats.sources.map((s) => s.label))}
      {stats.updated_at ? ` · updated ${timeAgo(stats.updated_at)}` : ""}
    </p>
  );
}
