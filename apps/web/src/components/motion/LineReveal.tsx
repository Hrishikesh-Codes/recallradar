"use client";

import { useEffect, useRef, type CSSProperties, type ReactNode } from "react";

type Props = {
  lines: ReactNode[];
  as?: "h1" | "h2" | "h3" | "p" | "div";
  className?: string;
  /**
   * "load": CSS-only slide-up on first paint (above the fold; works without JS).
   * "view": slides up when scrolled into view. Content stays visible if JS never runs, and
   * anything already on screen at hydration is never hidden.
   */
  trigger?: "load" | "view";
};

/** Masked line reveal: each line slides up from behind a clip, staggered. */
export function LineReveal({ lines, as: Tag = "div", className, trigger = "view" }: Props) {
  // One ref type that fits every allowed tag.
  const ref = useRef<HTMLHeadingElement & HTMLParagraphElement & HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (trigger !== "view" || !element) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (element.getBoundingClientRect().top < window.innerHeight) return;

    element.dataset.reveal = "armed";
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        delete element.dataset.reveal;
        observer.disconnect();
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    observer.observe(element);
    return () => {
      observer.disconnect();
      delete element.dataset.reveal;
    };
  }, [trigger]);

  return (
    <Tag ref={ref} className={className} data-reveal={trigger === "load" ? "on-load" : undefined}>
      {lines.map((line, index) => (
        <span
          key={index}
          className="reveal-line"
          style={{ "--line-index": index } as CSSProperties}
        >
          <span className="reveal-line__inner">{line}</span>
        </span>
      ))}
    </Tag>
  );
}
