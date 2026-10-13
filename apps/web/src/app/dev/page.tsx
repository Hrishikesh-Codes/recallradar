import type { Metadata } from "next";
import type { ReactNode } from "react";

import { OrbitIcon, RadarMark } from "@/components/icons";
import { LineReveal } from "@/components/motion/LineReveal";
import { Button, ButtonLink, TextLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DotGrid } from "@/components/ui/DotGrid";
import { Frame } from "@/components/ui/Frame";
import { StatusChip } from "@/components/ui/StatusChip";
import { TextField } from "@/components/ui/TextField";
import { VerdictHeading } from "@/components/ui/VerdictHeading";
import { VERDICTS, type Verdict } from "@/components/verdict";
import { contrastRatio, hexToRgb } from "@/design/contrast";
import { colors, type ColorToken } from "@/design/tokens";

export const metadata: Metadata = {
  title: "Design system",
  robots: { index: false, follow: false },
};

const VERDICT_ORDER = Object.keys(VERDICTS) as Verdict[];

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="border-t border-line py-14">
      <h2 id={id} className="eyebrow mb-8 text-muted-2">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Swatch({ name }: { name: ColorToken }) {
  const hex = colors[name];
  const ratio = contrastRatio(hexToRgb(hex), hexToRgb(colors["bg-0"]));
  return (
    <li className="flex flex-col gap-3">
      <span className="block h-20 rounded-md border border-line" style={{ backgroundColor: hex }} />
      <span className="text-caption">
        <span className="block font-medium">--{name}</span>
        <span className="block text-muted-2">
          {hex} · {ratio.toFixed(2)}:1 on bg-0
        </span>
      </span>
    </li>
  );
}

/** Living component gallery: every token and base component in one place (not indexed). */
export default function DesignSystemPage() {
  return (
    <div className="page-x pt-32 pb-16">
      <p className="eyebrow mb-6 text-accent">Design system</p>
      <h1 className="display mb-6 text-display">Tokens and components</h1>
      <p className="max-w-2xl text-muted-1">
        Colours, type, surfaces, and components used across RecallRadar. Values are measured from
        the design reference; contrast is enforced by unit tests. See docs/DESIGN.md.
      </p>

      <Section id="colours" title="Colour">
        <ul className="grid grid-cols-2 gap-6 sm:grid-cols-5">
          {(Object.keys(colors) as ColorToken[]).map((name) => (
            <Swatch key={name} name={name} />
          ))}
        </ul>
      </Section>

      <Section id="type" title="Type">
        <div className="flex flex-col gap-8">
          <p className="display text-hero">
            Hero <span className="text-accent">type</span>
          </p>
          <p className="display text-display">Display statement</p>
          <p className="text-heading font-medium">Secondary heading, text face</p>
          <p className="max-w-prose">
            Body copy is set in the text face at 15px with slightly negative tracking. It stays calm
            and plain, even when the news is bad.
          </p>
          <p className="text-caption text-muted-2">Caption and supporting detail.</p>
          <p className="eyebrow">Eyebrow label</p>
        </div>
      </Section>

      <Section id="buttons" title="Buttons and links">
        <div className="flex flex-wrap items-center gap-4">
          <Button variant="primary">Scan a product</Button>
          <Button>Paste a link</Button>
          <Button arrow={false}>No arrow</Button>
          <Button disabled>Disabled</Button>
          <ButtonLink href="/">Link styled as button</ButtonLink>
          <TextLink href="/">Text link</TextLink>
        </div>
      </Section>

      <Section id="fields" title="Fields">
        <div className="grid max-w-2xl gap-6">
          <TextField
            label="Describe your product"
            placeholder="Fisher-Price baby rocker, 2023"
            hint="Brand and model number give the most reliable result."
          />
          <TextField label="Search" hideLabel placeholder="Hidden label, still announced" />
        </div>
      </Section>

      <Section id="chips" title="Status chips">
        <div className="flex flex-wrap gap-3">
          {VERDICT_ORDER.map((verdict) => (
            <StatusChip key={verdict} verdict={verdict} />
          ))}
        </div>
      </Section>

      <Section id="verdicts" title="Verdicts">
        <div className="flex flex-col gap-16">
          {VERDICT_ORDER.map((verdict) => (
            <VerdictHeading key={verdict} verdict={verdict} as="h3" />
          ))}
        </div>
      </Section>

      <Section id="surfaces" title="Surfaces">
        <div className="grid gap-4 md:grid-cols-3">
          <Card innerClassName="flex flex-col gap-6 p-6">
            <OrbitIcon className="size-12 text-accent" />
            <div>
              <h3 className="mb-2 text-heading font-medium">Glass card</h3>
              <p className="text-muted-2">Hairline frame, 4px gap, dashed inner frame.</p>
            </div>
          </Card>
          <Card floating innerClassName="flex flex-col gap-3 p-6">
            <StatusChip verdict="recalled" className="self-start" />
            <h3 className="text-heading font-medium">Floating card</h3>
            <p className="text-muted-2">Adds the float shadow.</p>
          </Card>
          <div className="glass flex items-center gap-4 p-6">
            <RadarMark className="size-6 text-accent" />
            <span className="eyebrow">Glass control surface</span>
            <DotGrid className="ml-auto" />
          </div>
        </div>
      </Section>

      <Section id="frame" title="Nested frame">
        <Frame>
          <div className="frame__panel m-12 grid gap-2 p-2 md:grid-cols-2">
            <div className="frame__panel p-8">Panel</div>
            <div className="frame__panel p-8">Panel</div>
          </div>
        </Frame>
      </Section>

      <Section id="motion" title="Motion">
        <LineReveal
          as="p"
          className="display text-display"
          lines={[
            "Lines slide up",
            <span key="b" className="text-accent">
              when they scroll in
            </span>,
          ]}
        />
      </Section>
    </div>
  );
}
