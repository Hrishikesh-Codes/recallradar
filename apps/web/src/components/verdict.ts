import type { ComponentType, SVGProps } from "react";

import {
  AllClearIcon,
  CheckUnitIcon,
  NotCoveredIcon,
  RecalledIcon,
  UnidentifiedIcon,
} from "@/components/icons";

/**
 * The verdict states (SPEC §6.4 plus the approved "can't check yet" coverage state). Every state
 * has an icon and words, so colour is never the only signal.
 */
export type Verdict = "recalled" | "check_unit" | "all_clear" | "unidentified" | "not_covered";

type VerdictStyle = {
  label: string;
  /** Short form for list chips. */
  chip: string;
  colorClass: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  /** Plain-language meaning, for screen readers and tooltips. Never claims a product is safe. */
  meaning: string;
};

export const VERDICTS: Record<Verdict, VerdictStyle> = {
  recalled: {
    label: "Recalled",
    chip: "Recalled",
    colorClass: "text-accent-deep",
    Icon: RecalledIcon,
    meaning: "This product matches an official recall by its exact identifier.",
  },
  check_unit: {
    label: "Check your unit",
    chip: "Check unit",
    colorClass: "text-accent",
    Icon: CheckUnitIcon,
    meaning:
      "A recall may cover your product. Compare the details below with your label to be sure.",
  },
  all_clear: {
    label: "All clear",
    chip: "No recall found",
    colorClass: "text-text",
    Icon: AllClearIcon,
    meaning: "No recalls found for this product in the sources we checked.",
  },
  unidentified: {
    label: "Couldn't identify",
    chip: "Needs info",
    colorClass: "text-muted-2",
    Icon: UnidentifiedIcon,
    meaning: "We couldn't tell exactly what this is. A clearer photo or the model number helps.",
  },
  not_covered: {
    label: "Can't check yet",
    chip: "Not covered",
    colorClass: "text-muted-2",
    Icon: NotCoveredIcon,
    meaning: "This kind of product isn't covered by the recall sources we check yet.",
  },
};
