import type { MetadataRoute } from "next";

/** Installable app: opens straight to the check screen, in the app's dark colours. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "RecallRadar",
    short_name: "RecallRadar",
    description: "Check whether something you own has been recalled, with the evidence.",
    start_url: "/check",
    scope: "/",
    display: "standalone",
    background_color: "#010001",
    theme_color: "#010001",
    categories: ["utilities", "shopping", "lifestyle"],
    icons: [
      { src: "/icon/192", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon/512", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon/512", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Check a product", url: "/check" },
      { name: "My list", url: "/list" },
    ],
  };
}
