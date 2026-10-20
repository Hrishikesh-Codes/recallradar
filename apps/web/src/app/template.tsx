import { PageEnter } from "@/components/motion/PageEnter";

/** Re-mounted on every navigation, so each page after the first fades in (PageEnter). */
export default function Template({ children }: { children: React.ReactNode }) {
  return <PageEnter>{children}</PageEnter>;
}
