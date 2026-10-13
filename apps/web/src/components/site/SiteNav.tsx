"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { RadarMark } from "@/components/icons";
import { ScrambleText } from "@/components/motion/ScrambleText";
import { NAV_LINKS } from "@/components/site/navigation";
import { DotGrid } from "@/components/ui/DotGrid";
import { cn } from "@/lib/cn";

const HIDE_AFTER_PX = 120;

/**
 * Floating glass nav: wordmark pill + MENU pill, with a glass dropdown. Hides while scrolling
 * down and returns on scroll up or keyboard focus.
 */
export function SiteNav() {
  const [open, setOpen] = useState(false);
  const [scrolledAway, setScrolledAway] = useState(false);
  const menuId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let lastY = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      if (Math.abs(y - lastY) < 8) return;
      setScrolledAway(y > lastY && y > HIDE_AFTER_PX);
      lastY = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLAnchorElement>("a")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    };
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (panelRef.current?.contains(target) || buttonRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open]);

  const hidden = scrolledAway && !open;

  return (
    <header
      className={cn(
        "pointer-events-none fixed inset-x-0 top-0 z-50 flex justify-center pt-4",
        "transition-transform duration-500 ease-reveal",
        hidden && "-translate-y-[150%]",
      )}
      onFocusCapture={() => setScrolledAway(false)}
    >
      <div className="pointer-events-auto relative flex items-stretch gap-2">
        <Link
          href="/"
          className="glass flex items-center gap-2.5 px-5 py-3.5 sm:px-6"
          onClick={() => setOpen(false)}
        >
          <RadarMark className="size-5 text-accent" />
          <span className="display text-label font-semibold tracking-[0.01em]">RecallRadar</span>
        </Link>
        <button
          ref={buttonRef}
          type="button"
          className="glass eyebrow flex cursor-pointer items-center gap-4 px-5 py-3.5 sm:px-6"
          aria-expanded={open}
          aria-controls={menuId}
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
        >
          <ScrambleText text={open ? "Close" : "Menu"} className="w-12 text-left" />
          <DotGrid crossed={open} className="text-sm" />
        </button>

        <nav
          id={menuId}
          ref={panelRef}
          aria-label="Main"
          className={cn(
            "glass absolute top-[calc(100%+0.5rem)] left-1/2 w-64 -translate-x-1/2 py-3",
            "duration-(--dur-overlay) ease-out",
            // Visible at once when opening (so focus can move in); hidden only after the fade out.
            open
              ? "visible translate-y-0 opacity-100 transition-[opacity,translate]"
              : "invisible -translate-y-2 opacity-0 transition-[opacity,translate,visibility]",
          )}
        >
          <ul>
            {NAV_LINKS.map(({ href, label }, index) => (
              <li
                key={href}
                className={cn(
                  "transition-[opacity,translate] duration-(--dur-overlay) ease-out",
                  open ? "translate-y-0 opacity-100" : "-translate-y-1 opacity-0",
                )}
                style={{ transitionDelay: open ? `${index * 40}ms` : "0ms" }}
              >
                <Link
                  href={href}
                  className="eyebrow block px-6 py-3 text-center transition-colors duration-150 hover:text-accent"
                  onClick={() => setOpen(false)}
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
