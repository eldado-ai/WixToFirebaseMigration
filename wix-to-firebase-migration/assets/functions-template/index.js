/**
 * Contact form backend template for a site migrated off Wix.
 *
 * Replaces Wix's built-in form: receives a POST from the site's contact
 * form and emails it. No database -- the submission exists only as an
 * email unless you specifically add storage.
 *
 * Layers three independent spam defenses (see references/recaptcha.md and
 * references/contact-form.md for why each one is here):
 *   1. Honeypot field (hidden from real users, bots fill it in)
 *   2. In-memory per-IP rate limit
 *   3. reCAPTCHA v3 score check
 *
 * Before deploying, fill in the placeholders marked TODO below, and set
 * the required secrets:
 *   printf '%s' 'you@gmail.com' | firebase functions:secrets:set GMAIL_USER --data-file=-
 *   printf '%s' 'your-gmail-app-password' | firebase functions:secrets:set GMAIL_APP_PASSWORD --data-file=-
 *   printf '%s' 'your-recaptcha-secret-key' | firebase functions:secrets:set RECAPTCHA_SECRET --data-file=-
 *
 * And add the matching hosting rewrite in firebase.json:
 *   "rewrites": [{ "source": "/api/contact", "function": "sendContactEmail" }]
 */
const { onRequest } = require("firebase-functions/v2/https");
const { defineSecret } = require("firebase-functions/params");
const nodemailer = require("nodemailer");

const GMAIL_USER = defineSecret("GMAIL_USER");
const GMAIL_APP_PASSWORD = defineSecret("GMAIL_APP_PASSWORD");
const RECAPTCHA_SECRET = defineSecret("RECAPTCHA_SECRET");

// TODO: adjust to taste. 0.5 is a reasonable default for reCAPTCHA v3.
const RECAPTCHA_MIN_SCORE = 0.5;

// TODO: replace with the site's actual domains. Include the temporary
// *.web.app / *.firebaseapp.com domains during testing, and the real
// domain once the Phase 7 cutover happens -- don't remove the temporary
// ones afterward, they're harmless to leave and useful if you ever need
// to test against them again.
const ALLOWED_ORIGINS = [
  "https://YOUR-PROJECT.web.app",
  "https://YOUR-PROJECT.firebaseapp.com",
  "https://www.YOUR-DOMAIN.com",
  "https://YOUR-DOMAIN.com",
];

async function verifyRecaptcha(token, secret, ip) {
  if (!token) return { ok: false, reason: "missing-token" };

  const params = new URLSearchParams({ secret, response: token });
  if (ip && ip !== "unknown") params.append("remoteip", ip);

  const resp = await fetch("https://www.google.com/recaptcha/api/siteverify", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params.toString(),
  });

  const data = await resp.json();
  if (!data.success) {
    // If this fires with a "browser-error" reason and the domain list above
    // is definitely correct, the key is very likely an Enterprise-type key
    // rather than standard v3 -- see references/recaptcha.md.
    return { ok: false, reason: (data["error-codes"] || []).join(",") };
  }
  if (typeof data.score === "number" && data.score < RECAPTCHA_MIN_SCORE) {
    return { ok: false, reason: `low-score:${data.score}` };
  }
  return { ok: true, score: data.score };
}

// Very small in-memory rate limiter. Resets on cold start -- that's fine,
// it's a second layer of defense, not the only one.
const recentSubmissions = new Map();
const RATE_LIMIT_WINDOW_MS = 60 * 1000;
const RATE_LIMIT_MAX = 3;

function isRateLimited(ip) {
  const now = Date.now();
  const hits = (recentSubmissions.get(ip) || []).filter(
    (t) => now - t < RATE_LIMIT_WINDOW_MS
  );
  if (hits.length >= RATE_LIMIT_MAX) return true;
  hits.push(now);
  recentSubmissions.set(ip, hits);
  return false;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

exports.sendContactEmail = onRequest(
  {
    // TODO: set to the region that matches your data-residency needs.
    // The default is a US region -- this is easy to forget and won't
    // surface as a bug in testing, only as a fact about where data flows.
    region: "europe-west3",
    secrets: [GMAIL_USER, GMAIL_APP_PASSWORD, RECAPTCHA_SECRET],
    cors: ALLOWED_ORIGINS,
    maxInstances: 5,
  },
  async (req, res) => {
    if (req.method === "OPTIONS") {
      res.status(204).send("");
      return;
    }

    if (req.method !== "POST") {
      res.status(405).json({ ok: false, error: "Method not allowed" });
      return;
    }

    const ip =
      (req.headers["x-forwarded-for"] || "").split(",")[0].trim() ||
      req.ip ||
      "unknown";

    if (isRateLimited(ip)) {
      // TODO: translate this message if the site isn't in English.
      res.status(429).json({ ok: false, error: "Too many requests. Try again in a minute." });
      return;
    }

    const body = req.body || {};

    // Honeypot: a field that's hidden from real users via CSS but present
    // in the DOM. Bots that fill in every field submit it; real users never
    // see it. If it's filled, silently accept (200) without sending mail --
    // don't tell the bot it was rejected, so it gets no signal to adapt.
    if (body.website) {
      res.status(200).json({ ok: true });
      return;
    }

    const name = String(body.name || "").trim();
    const contact = String(body.contact || "").trim();
    const message = String(body.message || "").trim();

    if (name.length < 2 || contact.length < 5) {
      res.status(400).json({ ok: false, error: "Please fill in a valid name and contact info." });
      return;
    }
    if (name.length > 200 || contact.length > 200 || message.length > 5000) {
      res.status(400).json({ ok: false, error: "That text is too long." });
      return;
    }

    const captcha = await verifyRecaptcha(body.recaptchaToken, RECAPTCHA_SECRET.value(), ip);
    if (!captcha.ok) {
      console.warn("reCAPTCHA rejected:", captcha.reason);
      res.status(403).json({ ok: false, error: "Security check failed. Please refresh and try again." });
      return;
    }

    try {
      const transporter = nodemailer.createTransport({
        service: "gmail",
        auth: {
          user: GMAIL_USER.value(),
          pass: GMAIL_APP_PASSWORD.value(),
        },
      });

      await transporter.sendMail({
        // TODO: customize the from-name and subject line for the site.
        from: `"Website contact form" <${GMAIL_USER.value()}>`,
        to: GMAIL_USER.value(),
        replyTo: contact.includes("@") ? contact : undefined,
        subject: `New contact form submission — ${name}`,
        text: `Name: ${name}\nContact: ${contact}\n\nMessage:\n${message || "(no message)"}\n`,
        html: `
          <div style="font-family:Arial,sans-serif;line-height:1.6">
            <h2 style="margin:0 0 12px">New contact form submission</h2>
            <p><strong>Name:</strong> ${escapeHtml(name)}</p>
            <p><strong>Contact:</strong> ${escapeHtml(contact)}</p>
            <p><strong>Message:</strong><br>${
              message ? escapeHtml(message).replace(/\n/g, "<br>") : "<em>(no message)</em>"
            }</p>
          </div>
        `,
      });

      res.status(200).json({ ok: true });
    } catch (err) {
      console.error("sendContactEmail failed:", err);
      res.status(500).json({ ok: false, error: "Failed to send. Please try again later." });
    }
  }
);
