import type { Route } from "next";
import Link from "next/link";
import type { ComponentPropsWithoutRef, ReactNode } from "react";

import { ArrowRightIcon } from "@/components/icons";
import { cn } from "@/lib/cn";

type Variant = "outline" | "primary";

type StyleProps = {
  variant?: Variant;
  /** Leading arrow that slides through on hover. */
  arrow?: boolean;
  className?: string;
  children: ReactNode;
};

function classes(variant: Variant, className: string | undefined) {
  return cn("btn", variant === "primary" ? "btn--primary" : "btn--outline", className);
}

function Contents({ arrow, children }: { arrow: boolean; children: ReactNode }) {
  return (
    <>
      <span aria-hidden className="btn__bg btn__bg--rest" />
      <span aria-hidden className="btn__bg btn__bg--hover" />
      {arrow ? (
        <span aria-hidden className="btn__icon">
          <ArrowRightIcon className="btn__arrow btn__arrow--current" />
          <ArrowRightIcon className="btn__arrow btn__arrow--next" />
        </span>
      ) : null}
      <span>{children}</span>
    </>
  );
}

export function Button({
  variant = "outline",
  arrow = true,
  className,
  children,
  type = "button",
  ...props
}: StyleProps & Omit<ComponentPropsWithoutRef<"button">, keyof StyleProps>) {
  return (
    <button type={type} className={classes(variant, className)} {...props}>
      <Contents arrow={arrow}>{children}</Contents>
    </button>
  );
}

export function ButtonLink({
  variant = "outline",
  arrow = true,
  className,
  children,
  href,
  ...props
}: StyleProps & { href: Route } & Omit<ComponentPropsWithoutRef<"a">, keyof StyleProps | "href">) {
  return (
    <Link href={href} className={classes(variant, className)} {...props}>
      <Contents arrow={arrow}>{children}</Contents>
    </Link>
  );
}

export function TextLink({
  href,
  className,
  children,
  ...props
}: { href: Route; className?: string; children: ReactNode } & Omit<
  ComponentPropsWithoutRef<"a">,
  "href" | "className" | "children"
>) {
  return (
    <Link href={href} className={cn("text-link", className)} {...props}>
      <ArrowRightIcon aria-hidden className="size-[0.8em]" />
      <span>{children}</span>
    </Link>
  );
}
