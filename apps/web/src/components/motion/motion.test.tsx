import { act, render, screen } from "@testing-library/react";

import { LineReveal } from "@/components/motion/LineReveal";
import { ScrambleText } from "@/components/motion/ScrambleText";

function mockReducedMotion(reduce: boolean) {
  vi.spyOn(window, "matchMedia").mockImplementation(
    (query: string) =>
      ({
        matches: reduce && query.includes("reduce"),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("ScrambleText", () => {
  it("scrambles on change and settles on the new text", () => {
    mockReducedMotion(false);
    vi.useFakeTimers();
    const { rerender, container } = render(<ScrambleText text="Menu" />);
    expect(container).toHaveTextContent("Menu");

    rerender(<ScrambleText text="Close" />);
    act(() => vi.advanceTimersByTime(60));
    expect(container.textContent).not.toBe("Close");

    act(() => vi.advanceTimersByTime(1000));
    expect(container).toHaveTextContent("Close");
  });

  it("swaps instantly under reduced motion", () => {
    mockReducedMotion(true);
    const { rerender, container } = render(<ScrambleText text="Menu" />);
    rerender(<ScrambleText text="Close" />);
    expect(container).toHaveTextContent("Close");
  });

  it("is hidden from assistive tech (the control carries the label)", () => {
    mockReducedMotion(false);
    render(<ScrambleText text="Menu" />);
    expect(screen.getByText("Menu")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("LineReveal", () => {
  let observed: IntersectionObserverCallback | undefined;

  beforeEach(() => {
    observed = undefined;
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: IntersectionObserverCallback) {
          observed = callback;
        }
        observe() {}
        disconnect() {}
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders every line inside its mask, as one heading", () => {
    render(<LineReveal as="h2" lines={["First line", "Second line"]} />);
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent("First lineSecond line");
    expect(heading.querySelectorAll(".reveal-line")).toHaveLength(2);
  });

  it("uses the CSS on-load animation above the fold", () => {
    render(<LineReveal as="h1" trigger="load" lines={["Hero"]} />);
    expect(screen.getByRole("heading")).toHaveAttribute("data-reveal", "on-load");
  });

  it("never hides content that is already on screen", () => {
    mockReducedMotion(false);
    render(<LineReveal as="p" lines={["Visible"]} />);
    expect(screen.getByText("Visible").closest("p")).not.toHaveAttribute("data-reveal");
  });

  it("arms offscreen content and reveals it when it scrolls into view", () => {
    mockReducedMotion(false);
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      top: window.innerHeight + 200,
    } as DOMRect);
    render(<LineReveal as="p" lines={["Below the fold"]} />);
    const element = screen.getByText("Below the fold").closest("p");
    expect(element).toHaveAttribute("data-reveal", "armed");

    act(() => {
      observed?.(
        [{ isIntersecting: true } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    });
    expect(element).not.toHaveAttribute("data-reveal");
  });

  it("does nothing under reduced motion", () => {
    mockReducedMotion(true);
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      top: window.innerHeight + 200,
    } as DOMRect);
    render(<LineReveal as="p" lines={["Static"]} />);
    expect(screen.getByText("Static").closest("p")).not.toHaveAttribute("data-reveal");
  });
});
