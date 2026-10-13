import { Host_Grotesk, Inter } from "next/font/google";

/**
 * Free stand-ins for the reference's licensed faces (MSCHN, Suisse Int'l), picked from a
 * side-by-side comparison — see docs/DESIGN.md. Self-hosted by next/font: no requests to Google.
 */
export const displayFace = Host_Grotesk({
  subsets: ["latin"],
  variable: "--font-display-face",
  display: "swap",
});

export const textFace = Inter({
  subsets: ["latin"],
  variable: "--font-text-face",
  display: "swap",
});
