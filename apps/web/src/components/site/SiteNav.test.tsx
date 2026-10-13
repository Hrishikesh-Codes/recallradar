import { fireEvent, render, screen } from "@testing-library/react";

import { NAV_LINKS } from "@/components/site/navigation";
import { SiteNav } from "@/components/site/SiteNav";

describe("SiteNav menu", () => {
  it("is a disclosure button that controls the menu", () => {
    render(<SiteNav />);
    const button = screen.getByRole("button", { name: "Open menu" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    const menu = document.getElementById(button.getAttribute("aria-controls") ?? "");
    expect(menu).toHaveAttribute("aria-label", "Main");
  });

  it("opens, moves focus to the first link, and closes on Escape", () => {
    render(<SiteNav />);
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));

    const button = screen.getByRole("button", { name: "Close menu" });
    expect(button).toHaveAttribute("aria-expanded", "true");
    const first = NAV_LINKS[0];
    expect(document.activeElement).toHaveTextContent(first?.label ?? "");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("button", { name: "Open menu" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Open menu" }));
  });

  it("closes when clicking outside", () => {
    render(<SiteNav />);
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    fireEvent.pointerDown(document.body);
    expect(screen.getByRole("button", { name: "Open menu" })).toBeInTheDocument();
  });

  it("lists every nav link", () => {
    render(<SiteNav />);
    const menu = screen.getByRole("navigation", { name: "Main", hidden: true });
    for (const { label } of NAV_LINKS) {
      expect(menu).toHaveTextContent(label);
    }
  });
});
