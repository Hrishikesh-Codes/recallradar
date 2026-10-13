import type { SVGProps } from "react";

/** Our own line icons: 24×24, 1.5px stroke, currentColor. Decorative unless given a title. */
type IconProps = SVGProps<SVGSVGElement> & { title?: string };

function Icon({ title, children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      width="1em"
      height="1em"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <Icon {...props} viewBox="0 0 16 16" strokeWidth={1.6}>
      <path d="M1.5 8h12M9 3.5 13.5 8 9 12.5" />
    </Icon>
  );
}

/** Triangle with exclamation mark: RECALLED. */
export function RecalledIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 3.5 21.5 20h-19L12 3.5Z" />
      <path d="M12 10v4.5M12 17.25v.25" />
    </Icon>
  );
}

/** Label tag under a magnifier: CHECK YOUR UNIT. */
export function CheckUnitIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3.5 5.5h9l3 3.5-3 3.5h-9z" />
      <circle cx="16" cy="16" r="3.25" />
      <path d="m18.4 18.4 2.6 2.6" />
    </Icon>
  );
}

/** Circle with check: ALL CLEAR (no recall found; never "safe"). */
export function AllClearIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12.25 2.75 2.75L16 9.5" />
    </Icon>
  );
}

/** Circle with question mark: COULDN'T IDENTIFY. */
export function UnidentifiedIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.6 9.4a2.5 2.5 0 1 1 3.4 2.33c-.6.24-1 .8-1 1.45v.57M12 16.75V17" />
    </Icon>
  );
}

/** Dashed circle with a bar: CAN'T CHECK YET (category not covered by our sources). */
export function NotCoveredIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="9" strokeDasharray="2.5 2.5" />
      <path d="M8 12h8" />
    </Icon>
  );
}

/** Dotted orbits around a core; slowly rotates unless reduced motion is on. */
export function OrbitIcon(props: IconProps) {
  return (
    <Icon {...props} viewBox="0 0 48 48" strokeWidth={1.25}>
      <circle cx="24" cy="24" r="4" />
      <g className="origin-center motion-safe:animate-[spin_24s_linear_infinite]">
        <circle cx="24" cy="24" r="12" strokeDasharray="0.5 3.5" strokeWidth={2} />
      </g>
      <g className="origin-center motion-safe:animate-[spin_40s_linear_infinite_reverse]">
        <circle cx="24" cy="24" r="20" strokeDasharray="0.5 4.5" strokeWidth={2} />
      </g>
    </Icon>
  );
}

/** RecallRadar mark: concentric arcs around a dot, like a radar return. */
export function RadarMark(props: IconProps) {
  return (
    <Icon {...props} viewBox="0 0 32 32" strokeWidth={1.75}>
      <circle cx="16" cy="16" r="2.5" fill="currentColor" stroke="none" />
      <path d="M10.3 21.7a8 8 0 0 1 0-11.4M21.7 10.3a8 8 0 0 1 0 11.4" />
      <path d="M6.1 25.9a14 14 0 0 1 0-19.8M25.9 6.1a14 14 0 0 1 0 19.8" opacity="0.55" />
    </Icon>
  );
}
