import { formatCount, formatDate, listSources, timeAgo } from "@/lib/format";

describe("format", () => {
  it("lists sources in plain English, without repeats", () => {
    expect(listSources(["CPSC"])).toBe("CPSC");
    expect(listSources(["CPSC", "FDA", "FDA", "FDA"])).toBe("CPSC and FDA");
    expect(listSources(["CPSC", "FDA", "NHTSA"])).toBe("CPSC, FDA, and NHTSA");
  });

  it("says how long ago", () => {
    const now = new Date("2026-10-14T12:00:00Z");
    expect(timeAgo("2026-10-14T11:59:30Z", now)).toBe("just now");
    expect(timeAgo("2026-10-14T10:00:00Z", now)).toBe("2 hours ago");
    expect(timeAgo("2026-10-13T12:00:00Z", now)).toBe("yesterday");
  });

  it("formats calendar dates without shifting the day", () => {
    expect(formatDate("2025-06-12")).toBe("Jun 12, 2025");
    expect(formatCount(25856)).toBe("25,856");
  });
});
