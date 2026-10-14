import { RadarField } from "@/components/home/RadarField";
import { RecallCounter } from "@/components/home/RecallCounter";
import { TryIt } from "@/components/home/TryIt";
import { OrbitIcon } from "@/components/icons";
import { LineReveal } from "@/components/motion/LineReveal";
import { ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const STEPS = [
  {
    title: "Add it your way",
    body: "Scan a barcode, paste a product link, or describe it in a few words. No retailer account needed.",
  },
  {
    title: "We check official notices",
    body: "Your product is matched against federal recall notices, and we show exactly which fields matched and why.",
  },
  {
    title: "We keep watching",
    body: "Save it to your list. If a recall is announced later, you get one calm alert with what to do.",
  },
];

export default function HomePage() {
  return (
    <>
      <section className="page-x relative isolate flex min-h-svh flex-col justify-end overflow-clip pt-32 pb-16">
        <RadarField className="absolute inset-0 -z-10" />
        <div className="mb-8">
          <RecallCounter />
        </div>
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
        <div className="mt-10 flex flex-col gap-8 md:flex-row md:items-end md:justify-between">
          <p className="max-w-md text-muted-1">
            RecallRadar checks what you own against official U.S. recall notices, shows you the
            evidence, and keeps watching your list.
          </p>
          <div className="flex w-full max-w-xl flex-col gap-4">
            <TryIt />
            <div className="flex flex-wrap gap-3">
              <ButtonLink href="/check">Scan a barcode</ButtonLink>
              <ButtonLink href="/#how-it-works" arrow={false}>
                How it works
              </ButtonLink>
            </div>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="page-x scroll-mt-24 py-24">
        <p className="eyebrow mb-6 text-muted-2">How it works</p>
        <LineReveal
          as="h2"
          className="display mb-14 text-display text-balance"
          lines={["Three steps,", "and the evidence", "every time"]}
        />
        <ol className="grid gap-4 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <Card as="li" key={step.title} innerClassName="flex flex-col gap-10 p-6">
              <div className="flex items-start justify-between">
                <OrbitIcon className="size-12 text-accent" />
                <span className="eyebrow text-muted-2">0{index + 1}</span>
              </div>
              <div>
                <h3 className="mb-3 text-heading font-medium">{step.title}</h3>
                <p className="text-muted-2">{step.body}</p>
              </div>
            </Card>
          ))}
        </ol>
      </section>

      <section className="page-x py-32 text-center">
        <LineReveal
          as="h2"
          className="display text-display text-balance"
          lines={[
            "No recall found",
            "never means safe.",
            <span key="show" className="text-accent">
              We show what
            </span>,
            <span key="checked" className="text-accent">
              we checked.
            </span>,
          ]}
        />
      </section>
    </>
  );
}
