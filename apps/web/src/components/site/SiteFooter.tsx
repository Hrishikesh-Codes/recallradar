import Link from "next/link";

import { ArrowRightIcon, RadarMark } from "@/components/icons";
import { NAV_LINKS } from "@/components/site/navigation";
import { Frame } from "@/components/ui/Frame";
import { TextLink } from "@/components/ui/Button";

/** Footer in the reference's nested-frame style: frame > panel grid > bordered tiles. */
export function SiteFooter() {
  return (
    <footer>
      <Frame className="min-h-[25vh]">
        <div className="frame__panel mx-4 my-16 grid gap-2 rounded-lg p-2 sm:mx-[clamp(1rem,7.5vw,6rem)] md:grid-cols-[2fr_2fr_1fr] md:grid-rows-[auto_auto]">
          <nav aria-label="Footer" className="frame__panel md:row-span-2">
            <ul className="flex flex-col justify-evenly p-[clamp(1.5rem,1.148rem+1.502vw,2.5rem)]">
              {NAV_LINKS.map(({ href, label }) => (
                <li key={href} className="border-b border-line">
                  <Link
                    href={href}
                    className="flex items-center justify-between py-3 transition-colors duration-150 hover:text-accent"
                  >
                    {label}
                    <ArrowRightIcon className="size-3 text-muted-2" />
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="frame__panel flex items-center justify-center p-8">
            <TextLink href="/dev">Explore the design system</TextLink>
          </div>

          <Link
            href="/"
            aria-label="RecallRadar home"
            className="frame__panel order-first flex items-center justify-center gap-3 p-10 md:order-none"
          >
            <RadarMark className="size-8 text-accent" />
            <span className="display text-heading font-medium">RecallRadar</span>
          </Link>

          <div className="frame__panel flex flex-col items-center justify-evenly gap-3 p-5 text-center text-caption text-muted-2 sm:flex-row md:col-span-2">
            <p>Not affiliated with CPSC, FDA, USDA, or NHTSA.</p>
            <p>Always confirm with the official recall notice.</p>
            <p>RecallRadar is in development.</p>
          </div>
        </div>
      </Frame>
    </footer>
  );
}
