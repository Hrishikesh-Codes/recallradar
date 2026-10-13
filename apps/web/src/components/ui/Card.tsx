import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";

import { cn } from "@/lib/cn";

type CardProps<T extends ElementType> = {
  as?: T;
  floating?: boolean;
  className?: string;
  innerClassName?: string;
  children: ReactNode;
} & Omit<ComponentPropsWithoutRef<T>, "as" | "className" | "children">;

/** Glass card in the reference's nested style: hairline frame, 4px gap, dashed inner frame. */
export function Card<T extends ElementType = "div">({
  as,
  floating = false,
  className,
  innerClassName,
  children,
  ...props
}: CardProps<T>) {
  const Component: ElementType = as ?? "div";
  return (
    <Component className={cn("card", floating && "card--floating", className)} {...props}>
      <div className={cn("card__inner", innerClassName)}>{children}</div>
    </Component>
  );
}
