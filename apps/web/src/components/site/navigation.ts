import type { Route } from "next";

/** Site-wide links. Only routes that exist (typed routes fail the build otherwise). */
export const NAV_LINKS: ReadonlyArray<{ href: Route; label: string }> = [
  { href: "/", label: "Home" },
  { href: "/check", label: "Check a product" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/dev", label: "Design system" },
];
