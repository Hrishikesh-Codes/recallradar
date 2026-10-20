"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The orange phrase that changes as its section scrolls by, as on the reference ("interpret
 * intent" → …). Screen readers get the whole sentence once; the moving copy is hidden from them.
 */
export function EvidencePhrase({ phrases, sentence }: { phrases: string[]; sentence: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const element = ref.current;
    const section = element?.closest("section");
    if (!element || !section) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const rect = section.getBoundingClientRect();
      const travel = Math.max(1, rect.height - window.innerHeight);
      const progress = Math.min(1, Math.max(0, -rect.top / travel));
      setActive(Math.min(phrases.length - 1, Math.floor(progress * phrases.length)));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(frame);
    };
  }, [phrases.length]);

  return (
    <>
      <span className="sr-only">{sentence}</span>
      <span ref={ref} aria-hidden className="relative block overflow-clip text-accent">
        {/* The longest phrase holds the width; the others overlay it. */}
        <span className="invisible block">
          {phrases.reduce((a, b) => (b.length > a.length ? b : a), "")}
        </span>
        {phrases.map((phrase, index) => (
          <span
            key={phrase}
            className="absolute inset-0 block transition-transform duration-(--dur-reveal) ease-reveal"
            style={{
              transform: `translateY(${index === active ? 0 : index < active ? -110 : 110}%)`,
            }}
          >
            {phrase}
          </span>
        ))}
      </span>
    </>
  );
}
