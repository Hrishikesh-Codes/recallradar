import type { Route } from "next";

/** Site-wide links. Only routes that exist; M1 adds Check, My List, and Privacy. */
export const NAV_LINKS: ReadonlyArray<{ href: Route; label: string }> = [
  { href: "/", label: "Home" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/dev", label: "Design system" },
];
