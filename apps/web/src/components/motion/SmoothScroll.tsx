"use client";

import Lenis from "lenis";
import "lenis/dist/lenis.css";
import { useEffect } from "react";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";

/** Lenis smooth scrolling for marketing pages only; off under reduced motion. */
export function SmoothScroll() {
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (reducedMotion) return;
    const lenis = new Lenis({ autoRaf: true, anchors: true });
    return () => lenis.destroy();
  }, [reducedMotion]);

  return null;
}
