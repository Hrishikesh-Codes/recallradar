import { ImageResponse } from "next/og";

import { RadarIcon } from "@/components/pwa/RadarIcon";

const SIZES = [32, 192, 512] as const;

export function generateImageMetadata() {
  return SIZES.map((size) => ({
    id: String(size),
    size: { width: size, height: size },
    contentType: "image/png",
  }));
}

export default async function Icon({ id }: { id: Promise<string> }) {
  const size = Number(await id);
  return new ImageResponse(<RadarIcon size={size} />, { width: size, height: size });
}
