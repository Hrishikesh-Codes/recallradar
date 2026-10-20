import { render } from "@testing-library/react";

import { MenuDots } from "@/components/site/MenuDots";
import { PageHeader } from "@/components/site/PageHeader";

function visibleDots(container: HTMLElement) {
  return Array.from(container.querySelectorAll("span > span")).filter(
    (dot) => !dot.className.includes("opacity-0"),
  ).length;
}

describe("MenuDots", () => {
  it("is a 4×3 grid that keeps the six dots of a dotted × when open", () => {
    const closed = render(<MenuDots open={false} />);
    expect(visibleDots(closed.container)).toBe(12);
    const open = render(<MenuDots open />);
    expect(visibleDots(open.container)).toBe(6);
  });
});

describe("PageHeader", () => {
  it("keeps the words of a multi-line headline apart", () => {
    const { getByRole } = render(
      <PageHeader eyebrow="My list" title={["Keep watch on", "what you own"]} />,
    );
    expect(getByRole("heading", { level: 1 }).textContent).toBe("Keep watch on what you own");
  });
});
