const numberFormat = new Intl.NumberFormat("en-US");

export function formatCount(value: number): string {
  return numberFormat.format(value);
}

/** "CPSC", "CPSC and FDA", "CPSC, FDA, and NHTSA" (labels deduplicated, order kept). */
export function listSources(labels: readonly string[]): string {
  const unique = [...new Set(labels)];
  if (unique.length <= 2) return unique.join(" and ");
  return `${unique.slice(0, -1).join(", ")}, and ${unique.at(-1)}`;
}

const UNITS: ReadonlyArray<[Intl.RelativeTimeFormatUnit, number]> = [
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];
const relative = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });

/** "2 hours ago", "yesterday", "just now". */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

const dateFormat = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

/** API dates are calendar dates ("2025-06-12"); format them without shifting time zones. */
export function formatDate(isoDate: string): string {
  return dateFormat.format(new Date(`${isoDate.slice(0, 10)}T00:00:00Z`));
}
