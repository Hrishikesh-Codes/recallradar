import { render, screen } from "@testing-library/react";

import { Button, ButtonLink, TextLink } from "@/components/ui/Button";

describe("Button", () => {
  it("is a non-submitting button named by its label", () => {
    render(<Button variant="primary">Scan a product</Button>);
    const button = screen.getByRole("button", { name: "Scan a product" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveClass("btn", "btn--primary");
  });

  it("keeps the decorative layers and arrows out of the accessibility tree", () => {
    const { container } = render(<Button>Paste a link</Button>);
    for (const decoration of container.querySelectorAll(".btn__bg, .btn__icon")) {
      expect(decoration).toHaveAttribute("aria-hidden", "true");
    }
    expect(screen.getByRole("button")).toHaveAccessibleName("Paste a link");
  });

  it("can drop the arrow", () => {
    const { container } = render(<Button arrow={false}>Plain</Button>);
    expect(container.querySelector(".btn__icon")).toBeNull();
  });
});

describe("links", () => {
  it("ButtonLink renders an anchor with the button styling", () => {
    render(<ButtonLink href="/dev">Design system</ButtonLink>);
    const link = screen.getByRole("link", { name: "Design system" });
    expect(link).toHaveAttribute("href", "/dev");
    expect(link).toHaveClass("btn", "btn--outline");
  });

  it("TextLink renders an underlined uppercase link", () => {
    render(<TextLink href="/">Home</TextLink>);
    expect(screen.getByRole("link", { name: "Home" })).toHaveClass("text-link");
  });
});
