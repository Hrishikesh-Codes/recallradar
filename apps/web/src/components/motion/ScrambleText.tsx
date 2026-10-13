"use client";

import { useEffect, useRef, useState } from "react";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";

const GLYPHS = "█▓▒░▚▞▙▟▛▜▄▀";
const FRAMES = 10;
const FRAME_MS = 30;

/**
 * When `text` changes, letters resolve from block glyphs left to right (the reference's
 * MENU -> CLOSE effect). Purely visual: it is aria-hidden, so give the control its own label.
 */
export function ScrambleText({ text, className }: { text: string; className?: string }) {
  const [scrambled, setScrambled] = useState<string | null>(null);
  const reducedMotion = usePrefersReducedMotion();
  const previous = useRef(text);

  useEffect(() => {
    if (previous.current === text || reducedMotion) {
      previous.current = text;
      return;
    }
    previous.current = text;
    let frame = 0;
    const timer = window.setInterval(() => {
      frame += 1;
      if (frame >= FRAMES) {
        window.clearInterval(timer);
        setScrambled(null);
        return;
      }
      const settled = Math.floor((frame / FRAMES) * text.length);
      setScrambled(
        Array.from(text, (char, i) =>
          i < settled ? char : (GLYPHS[Math.floor(Math.random() * GLYPHS.length)] ?? char),
        ).join(""),
      );
    }, FRAME_MS);
    return () => window.clearInterval(timer);
  }, [text, reducedMotion]);

  return (
    <span aria-hidden className={className}>
      {reducedMotion ? text : (scrambled ?? text)}
    </span>
  );
}
