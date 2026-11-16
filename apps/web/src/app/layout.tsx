import type { Metadata, Viewport } from "next";

import { displayFace, textFace } from "@/app/fonts";
import { SiteFooter } from "@/components/site/SiteFooter";
import { ServiceWorker } from "@/components/pwa/ServiceWorker";
import { SiteNav } from "@/components/site/SiteNav";
import { cn } from "@/lib/cn";
import { SITE_DESCRIPTION, SITE_URL } from "@/lib/site";

import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "RecallRadar", template: "%s · RecallRadar" },
  description: SITE_DESCRIPTION,
  applicationName: "RecallRadar",
  // Each page is its own canonical URL (resolved against metadataBase and the page's path).
  alternates: { canonical: "./" },
  openGraph: {
    type: "website",
    siteName: "RecallRadar",
    title: "RecallRadar: know if what you own was recalled",
    description: SITE_DESCRIPTION,
    url: "./",
  },
  twitter: {
    card: "summary_large_image",
    title: "RecallRadar: know if what you own was recalled",
    description: SITE_DESCRIPTION,
  },
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
        <ServiceWorker />
      </body>
    </html>
  );
}
