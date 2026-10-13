import { SmoothScroll } from "@/components/motion/SmoothScroll";

export default function MarketingLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      <SmoothScroll />
      {children}
    </>
  );
}
