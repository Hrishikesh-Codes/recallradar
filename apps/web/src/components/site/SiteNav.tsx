"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { RadarMark } from "@/components/icons";
import { ScrambleText } from "@/components/motion/ScrambleText";
import { NAV_LINKS } from "@/components/site/navigation";
import { MenuDots } from "@/components/site/MenuDots";
import { cn } from "@/lib/cn";

/**
 * Floating glass nav, as on the reference: wordmark pill + MENU pill, always in view, and a glass
 * panel the width of both that opens downwards (its height grows with the reveal easing).
 */
export function SiteNav() {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);

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

  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-50 flex justify-center pt-6">
      <div className="pointer-events-auto relative grid grid-cols-[auto_auto] gap-2">
        <Link
          href="/"
          className="glass flex h-14 items-center gap-2.5 px-6"
          onClick={() => setOpen(false)}
        >
          <RadarMark className="size-5 text-accent" />
          <span className="display text-label font-semibold tracking-[0.01em]">RecallRadar</span>
        </Link>
        <button
          ref={buttonRef}
          type="button"
          className="glass eyebrow flex h-14 cursor-pointer items-center gap-4 px-6"
          aria-expanded={open}
          aria-controls={menuId}
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
        >
          <ScrambleText text={open ? "Close" : "Menu"} className="w-11 text-left" />
          <MenuDots open={open} />
        </button>

        {/* Height reveal: grid rows 0fr → 1fr. Visible at once when opening, so focus can move
            in; hidden only after the close animation. */}
        <div
          className={cn(
            "absolute inset-x-0 top-[calc(100%+0.5rem)] grid",
            "duration-(--dur-reveal) ease-reveal",
            // Visibility switches at once on opening (focus moves in on the first frame) and
            // only after the close animation.
            open
              ? "visible grid-rows-[1fr] transition-[grid-template-rows]"
              : "invisible grid-rows-[0fr] transition-[grid-template-rows,visibility]",
          )}
        >
          <nav
            id={menuId}
            ref={panelRef}
            aria-label="Main"
            className="glass min-h-0 overflow-hidden"
          >
            <ul className="py-3.5">
              {NAV_LINKS.map(({ href, label }) => (
                <li key={href}>
                  <Link
                    href={href}
                    className="eyebrow block px-6 py-2 text-center leading-[1.9] transition-colors duration-150 hover:text-accent"
                    onClick={() => setOpen(false)}
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </div>
    </header>
  );
}
