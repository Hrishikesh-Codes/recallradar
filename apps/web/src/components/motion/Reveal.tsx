"use client";

import { useEffect, useRef, type CSSProperties, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type Props = {
  as?: "div" | "li";
  /** Position in a group, for the 80ms stagger. */
  index?: number;
  className?: string;
  children: ReactNode;
};

/**
 * A block that fades and slides up into place as it scrolls into view (cards, buttons), as on
 * the reference. Like LineReveal, only content that starts offscreen is ever hidden, and
 * nothing moves under reduced motion.
 */
export function Reveal({ as: Tag = "div", index = 0, className, children }: Props) {
  const ref = useRef<HTMLDivElement & HTMLLIElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (element.getBoundingClientRect().top < window.innerHeight) return;

    element.dataset.revealBlock = "armed";
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        element.dataset.revealBlock = "in";
        observer.disconnect();
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(element);
    return () => {
      observer.disconnect();
      delete element.dataset.revealBlock;
    };
  }, []);

  return (
    <Tag
      ref={ref}
      className={cn("reveal-block", className)}
      style={{ "--reveal-index": index } as CSSProperties}
    >
      {children}
    </Tag>
  );
}
