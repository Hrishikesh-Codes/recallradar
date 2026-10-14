import "server-only";

import nodemailer from "nodemailer";

/**
 * Outgoing mail over SMTP: Mailpit locally (smtp://localhost:1025, view at localhost:8025),
 * Resend in production (smtps://resend:API_KEY@smtp.resend.com:465).
 */
const transport = nodemailer.createTransport(process.env.SMTP_URL ?? "smtp://localhost:1025");
const from = process.env.MAIL_FROM ?? "RecallRadar <sign-in@localhost>";

export async function sendSignInLink(email: string, url: string): Promise<void> {
  await transport.sendMail({
    from,
    to: email,
    subject: "Your RecallRadar sign-in link",
    text: [
      "Hello,",
      "",
      "Use this link to sign in to RecallRadar. It works once and expires in 15 minutes.",
      "",
      url,
      "",
      "If you didn't ask for it, ignore this email; nobody can sign in without the link.",
    ].join("\n"),
    html: `<p>Hello,</p><p>Use this link to sign in to RecallRadar. It works once and expires in 15 minutes.</p><p><a href="${url}">Sign in to RecallRadar</a></p><p style="color:#555;font-size:13px">If you didn't ask for it, ignore this email; nobody can sign in without the link.</p>`,
  });
}
