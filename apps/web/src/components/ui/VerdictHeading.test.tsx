import { render, screen } from "@testing-library/react";

import { StatusChip } from "@/components/ui/StatusChip";
import { VerdictHeading } from "@/components/ui/VerdictHeading";
import { VERDICTS, type Verdict } from "@/components/verdict";

const ALL = Object.keys(VERDICTS) as Verdict[];

describe("VerdictHeading", () => {
  it.each(ALL)("%s says it in words, not just colour", (verdict) => {
    const { container } = render(<VerdictHeading verdict={verdict} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(VERDICTS[verdict].label);
    expect(screen.getByText(VERDICTS[verdict].meaning)).toBeInTheDocument();
    // The icon is decoration; the words carry the meaning.
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("renders at the requested heading level", () => {
    render(<VerdictHeading verdict="recalled" as="h2" />);
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Recalled");
  });
});

describe("verdict copy never overclaims (SPEC §0.8, §6.4)", () => {
  it.each(ALL)("%s never calls a product safe", (verdict) => {
    const { label, chip, meaning } = VERDICTS[verdict];
    for (const text of [label, chip, meaning]) {
      expect(text).not.toMatch(/\bsafe\b/i);
    }
  });

  it("all clear is phrased as 'no recalls found'", () => {
    expect(VERDICTS.all_clear.meaning).toMatch(/^No recalls found/);
    expect(VERDICTS.all_clear.chip).toBe("No recall found");
  });
});

describe("StatusChip", () => {
  it.each(ALL)("%s shows its short label with the full meaning as a tooltip", (verdict) => {
    render(<StatusChip verdict={verdict} />);
    const chip = screen.getByText(VERDICTS[verdict].chip);
    expect(chip).toHaveAttribute("title", VERDICTS[verdict].meaning);
  });
});
