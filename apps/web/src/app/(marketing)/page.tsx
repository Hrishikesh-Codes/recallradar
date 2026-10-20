import { DotField } from "@/components/field/DotField";
import { EvidencePhrase } from "@/components/home/EvidencePhrase";
import { RecallCounter } from "@/components/home/RecallCounter";
import { ScrollCue } from "@/components/home/ScrollCue";
import { CheckStepIcon, ScanStepIcon, WatchStepIcon } from "@/components/home/StepIcons";
import { StickyStatement, type Note } from "@/components/home/StickyStatement";
import { TryIt } from "@/components/home/TryIt";
import { LineReveal } from "@/components/motion/LineReveal";
import { Reveal } from "@/components/motion/Reveal";
import { ButtonLink } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

/*
 * The landing page follows the reference's rhythm: a hero over our own procedural imagery, a
 * pinned statement over the halftone grid with notes drifting past, a second statement over the
 * dot cloud, the how-it-works cards over the spinning globe, a large statement over the radar
 * rings, and a closing call to action over the imagery again. Each section names the field
 * formation it wants (DotField reads `data-field`).
 */

const NOTES: Note[] = [
  {
    text: "Recall notices from CPSC, FDA, USDA FSIS and NHTSA, refreshed every day.",
    side: "right",
    at: 0.16,
  },
  {
    text: "Barcodes, model numbers and lot codes are matched exactly, never guessed.",
    side: "left",
    at: 0.36,
  },
  {
    text: "Cars, car seats and tires are matched by VIN, make, model and year.",
    side: "right",
    at: 0.56,
  },
  {
    text: "Every answer shows which fields matched and what to check on your label.",
    side: "left",
    at: 0.74,
  },
];

const STEPS = [
  {
    Icon: ScanStepIcon,
    title: "Add it your way",
    body: "Scan a barcode, paste a product link, photograph a label, or describe it in a few words. No retailer account needed.",
  },
  {
    Icon: CheckStepIcon,
    title: "We check official notices",
    body: "Your product is matched against federal recall notices, and we show exactly which fields matched and why.",
  },
  {
    Icon: WatchStepIcon,
    title: "We keep watching",
    body: "Save it to your list. If a recall is announced later, you get one calm alert with what to do.",
  },
];

export default function HomePage() {
  return (
    <>
      <DotField />

      <section
        data-field="panels"
        className="field-panels page-x relative z-[1] flex min-h-svh flex-col justify-end pt-32 pb-10"
      >
        <div data-field-shade className="mb-8 self-start">
          <RecallCounter />
        </div>
        <div data-field-shade="large" className="self-start">
          <LineReveal
            as="h1"
            trigger="load"
            className="display text-hero"
            lines={[
              "Know if what",
              "you own was",
              <span key="recalled" className="ml-[0.6em] inline-block text-accent">
                recalled
              </span>,
            ]}
          />
        </div>
        <div className="mt-10 flex flex-col gap-8 md:flex-row md:items-end md:justify-between">
          <p data-field-shade className="max-w-md text-text">
            RecallRadar checks what you own against official U.S. recall notices, shows you the
            evidence, and keeps watching your list.
          </p>
          <div data-field-shade className="flex w-full max-w-xl flex-col gap-4">
            <TryIt />
            <div className="flex flex-wrap gap-3">
              <ButtonLink href="/check">Scan a barcode</ButtonLink>
              <ButtonLink href="/#how-it-works" arrow={false}>
                How it works
              </ButtonLink>
            </div>
          </div>
        </div>
        <ScrollCue className="mt-10 hidden justify-end md:flex" />
      </section>

      <StickyStatement field="grid" screens={3} notes={NOTES}>
        <LineReveal
          as="h2"
          className="statement max-w-[34rem]"
          lines={[
            "Every official recall notice,",
            "checked against what you own.",
            "Know what to do next.",
          ]}
        />
      </StickyStatement>

      <StickyStatement field="cloud" screens={2}>
        <h2 className="statement max-w-[34rem]">
          <span aria-hidden className="block">
            Every answer shows its evidence,
          </span>
          <span aria-hidden className="block">
            so you know
          </span>
          <EvidencePhrase
            phrases={["what matched", "what to check", "what to do next"]}
            sentence="Every answer shows its evidence, so you know what matched, what to check, and what to do next."
          />
        </h2>
        <Reveal className="mt-10">
          <ButtonLink href="/#how-it-works">How it works</ButtonLink>
        </Reveal>
      </StickyStatement>

      <section
        id="how-it-works"
        data-field="torus"
        className="page-x relative z-[1] flex min-h-svh scroll-mt-24 flex-col justify-center gap-[clamp(3rem,8vw,7rem)] py-24"
      >
        <h2 className="text-center text-label font-medium tracking-normal text-muted-2 uppercase">
          How it works
        </h2>
        <ol className="mx-auto grid w-full max-w-[66rem] gap-4 md:grid-cols-3">
          {STEPS.map(({ Icon, title, body }, index) => (
            <Reveal
              as="li"
              key={title}
              index={index}
              className={cn(
                "card-plain flex flex-col gap-16",
                index === 1 && "md:translate-y-12",
                index === 2 && "md:translate-y-24",
              )}
            >
              <Icon className="size-[5.5rem] text-accent" />
              <div>
                <h3 className="mb-4 text-[1.125rem] leading-[1.2] font-medium tracking-[-0.02em]">
                  {title}
                </h3>
                <p className="text-khaki">{body}</p>
              </div>
            </Reveal>
          ))}
        </ol>
      </section>

      <section
        data-field="rings"
        className="page-x relative z-[1] flex min-h-svh items-center justify-center py-24 text-center"
      >
        <div data-field-shade="large">
          <LineReveal
            as="h2"
            className="display text-statement"
            lines={[
              "No recall found",
              "never means safe.",
              <span key="show" className="text-accent">
                We show what
              </span>,
              "we checked.",
            ]}
          />
        </div>
      </section>

      <section
        data-field="panels"
        className="field-panels page-x relative z-[1] flex min-h-svh flex-col items-center justify-center py-24 text-center"
      >
        <div data-field-shade className="flex w-full max-w-xl flex-col items-center gap-10">
          <LineReveal
            as="h2"
            className="statement"
            lines={["Check something you own.", "It takes a few seconds."]}
          />
          <Reveal className="w-full">
            <TryIt id="try-it-again" label="Something you own: product, link, barcode, or VIN" />
          </Reveal>
        </div>
      </section>
    </>
  );
}
