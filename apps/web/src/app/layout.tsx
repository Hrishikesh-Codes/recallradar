import type { Metadata, Viewport } from "next";

import { displayFace, textFace } from "@/app/fonts";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteNav } from "@/components/site/SiteNav";
import { cn } from "@/lib/cn";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "RecallRadar", template: "%s · RecallRadar" },
  description:
    "Check whether something you own has been recalled, with evidence from official recall notices.",
};

export const viewport: Viewport = {
  themeColor: "#010001",
  colorScheme: "dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={cn(displayFace.variable, textFace.variable)}>
      <body>
        <a
          href="#main"
          className="glass eyebrow sr-only z-[60] px-4 py-3 focus:not-sr-only focus:fixed focus:top-4 focus:left-4"
        >
          Skip to content
        </a>
        <SiteNav />
        <main id="main">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
