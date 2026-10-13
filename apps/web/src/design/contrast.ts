/** WCAG 2.x contrast maths (https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio). */

type Rgb = readonly [number, number, number];

export function hexToRgb(hex: string): Rgb {
  const match = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!match?.[1]) throw new Error(`Expected #rrggbb, got ${hex}`);
  const value = Number.parseInt(match[1], 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance([r, g, b]: Rgb): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrastRatio(a: Rgb, b: Rgb): number {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x) as [
    number,
    number,
  ];
  return (hi + 0.05) / (lo + 0.05);
}

/** The colour you see when `top` at `alpha` sits over an opaque `bottom`. */
export function composite(top: Rgb, alpha: number, bottom: Rgb): Rgb {
  const mix = (t: number, b: number) => Math.round(t * alpha + b * (1 - alpha));
  return [mix(top[0], bottom[0]), mix(top[1], bottom[1]), mix(top[2], bottom[2])];
}
