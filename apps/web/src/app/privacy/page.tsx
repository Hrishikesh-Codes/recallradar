import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy",
  description: "What RecallRadar stores, why, and how to delete it.",
};

const SECTIONS: ReadonlyArray<{ title: string; body: string[] }> = [
  {
    title: "Checking a product (no account)",
    body: [
      "We don't store what you check. We record only that a check happened: the input type (text, link, or barcode), the verdict, how many recalls matched, and how long it took. These counts are how we measure the service.",
      "To stop abuse, the API counts requests per network address in memory for up to a day. Addresses are never written to our database.",
      "Product links: we read the words in the link itself. We never open store pages, and we never ask for store passwords.",
      "Barcodes: if a recall doesn't list the barcode, our server may look up the product name on Open Food Facts. Your address isn't sent to them, and we keep the result (the barcode and product name) so we don't ask twice.",
    ],
  },
  {
    title: "Feedback",
    body: [
      "When you answer “This is mine”, “Not my product”, or “Already handled”, we keep that answer with what was checked (product name, brand, model, barcode) to improve matching. It isn't linked to you or your account.",
    ],
  },
  {
    title: "Your account and list",
    body: [
      "Sign-in is by email link, so we store your email address, and the links themselves only in hashed form until they're used or expire (15 minutes). There are no passwords.",
      "For your list we store what you typed, pasted, or scanned for each item, its name, any purchase date you add, the recalls that match it, your answers, and which alerts we sent. Your sign-in session stores your browser's user agent, not your address.",
      "Demo accounts (“Try the demo”) have no email and are deleted after 7 days.",
      "We never store payment details, home addresses, or retailer passwords.",
    ],
  },
  {
    title: "Email",
    body: [
      "If a CPSC recall newly matches something on your list, we email you once per item and recall. You can turn this off on your account page. FDA recalls aren't emailed (openFDA's terms rule it out); they show on your list.",
    ],
  },
  {
    title: "Who handles your data",
    body: [
      "Neon (database), Vercel (website), Hugging Face (API), Resend (email), and Sentry (error reports, configured to exclude personal data). Each processes data only to run their part of the service. Nothing is sold or shared for advertising, and we use no analytics or tracking cookies: the only cookie is your sign-in session.",
    ],
  },
  {
    title: "Export and delete",
    body: [
      "On your account page you can download everything we hold about you as a JSON file, and delete your account. Deleting removes your account, list, matches, and alert history at once.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <section className="page-x flex min-h-svh flex-col gap-12 pt-32 pb-24">
      <header className="max-w-3xl">
        <p className="eyebrow mb-4 text-muted-2">Privacy</p>
        <h1 className="display text-display text-balance">What we keep, and why</h1>
        <p className="mt-4 text-muted-2">Last updated October 2026.</p>
      </header>
      <div className="flex max-w-3xl flex-col gap-10">
        {SECTIONS.map((section) => (
          <section key={section.title} className="flex flex-col gap-3">
            <h2 className="text-heading font-medium">{section.title}</h2>
            {section.body.map((paragraph) => (
              <p key={paragraph} className="text-muted-1">
                {paragraph}
              </p>
            ))}
          </section>
        ))}
      </div>
    </section>
  );
}
