import { composite, contrastRatio, hexToRgb, relativeLuminance } from "@/design/contrast";

describe("contrast maths", () => {
  it("parses hex colours", () => {
    expect(hexToRgb("#ff9d00")).toEqual([255, 157, 0]);
    expect(() => hexToRgb("orange")).toThrow();
  });

  it("matches the WCAG reference points", () => {
    expect(relativeLuminance([255, 255, 255])).toBeCloseTo(1);
    expect(relativeLuminance([0, 0, 0])).toBe(0);
    expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21);
    expect(contrastRatio([119, 119, 119], [255, 255, 255])).toBeCloseTo(4.48, 2);
  });

  it("is symmetric", () => {
    expect(contrastRatio([1, 0, 1], [238, 234, 220])).toBe(
      contrastRatio([238, 234, 220], [1, 0, 1]),
    );
  });

  it("composites a translucent colour over an opaque one", () => {
    expect(composite([255, 255, 255], 0.5, [0, 0, 0])).toEqual([128, 128, 128]);
    expect(composite([49, 44, 33], 0.3, [1, 0, 1])).toEqual([15, 13, 11]);
  });
});
