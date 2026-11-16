import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

/** Public pages are indexable; account pages and internals aren't worth crawling. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/account", "/list", "/api/", "/dev", "/offline"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
