"use client";

import { useState, type ReactNode } from "react";

// Survives navigations (the module stays loaded), unlike component state.
let firstPageShown = false;

/**
 * Fades a page in after a navigation, as on the reference. The first page of a visit doesn't
 * fade: it has its own load-in (line reveals), and the server renders it without the class.
 */
export function PageEnter({ children }: { children: ReactNode }) {
  const [animate] = useState(() => {
    const navigated = firstPageShown;
    if (typeof window !== "undefined") firstPageShown = true;
    return navigated;
  });
  return <div className={animate ? "page-enter" : undefined}>{children}</div>;
}
