# Contact form backend

Wix's built-in form (submission storage, spam filtering, email notification) has no equivalent once the site leaves Wix. The replacement is a small Cloud Function that receives a POST from the form and sends an email — no database needed unless the user specifically wants a stored submission history.

A working template is in `assets/functions-template/index.js`. This document explains the decisions behind it.

## Why a Cloud Function instead of a form service (Formspree, etc.)

Both are legitimate. The tradeoff to actually discuss with the user:

- **Third-party form service**: faster to set up, no backend code, but submissions transit and often persist on that service's infrastructure — a separate data processor the user may not have considered.
- **Cloud Function you own**: more setup, but the data path is fully within infrastructure the user already controls (their own Google/Firebase project, their own email).

For sites handling anything sensitive — health, legal, financial, or otherwise personal submissions — raise this distinction explicitly rather than defaulting silently to whichever is easier to build. Let the user decide with the tradeoff in front of them.

## Required pieces

**Region.** Set it explicitly:

```js
exports.sendContactEmail = onRequest(
  { region: "europe-west3", ... },
  handler
);
```

The default region is in the US. If the user is in the EU or otherwise cares about data residency, this is a one-line fix now and a hard-to-notice gap later — nothing in testing will surface a wrong region, since the function works identically regardless of where it runs.

**Secrets, never inline.** Mail credentials go through Secret Manager:

```js
const { defineSecret } = require("firebase-functions/params");
const GMAIL_USER = defineSecret("GMAIL_USER");
const GMAIL_APP_PASSWORD = defineSecret("GMAIL_APP_PASSWORD");
```

Set values without echoing them to shell history or terminal output:

```bash
printf '%s' 'the-value' | firebase functions:secrets:set GMAIL_APP_PASSWORD --data-file=-
```

If sending through Gmail, this must be a Gmail **app password** (Google Account -> Security -> App passwords), not the account login password — Gmail rejects SMTP auth with the real password by default.

**Hosting rewrite**, so the frontend can `fetch('/api/contact')` same-origin with no CORS complexity:

```json
{
  "hosting": {
    "rewrites": [{ "source": "/api/contact", "function": "sendContactEmail" }]
  }
}
```

**CORS allowlist**, even with the rewrite in place — belt and suspenders, and needed if the function is ever called directly:

```js
cors: [
  "https://<project>.web.app",
  "https://<project>.firebaseapp.com",
  "https://www.<final-domain>",
  "https://<final-domain>",
]
```

Include both the temporary Firebase domains and the eventual real domain from the start — the form gets tested on `*.web.app` long before the domain cutover happens.

## Defense in depth against spam

Layer three independent, cheap mechanisms rather than relying on any single one — see `references/recaptcha.md` for the reCAPTCHA piece specifically:

1. **Honeypot field** — a form field hidden from real users that bots fill in anyway. If it's non-empty, silently accept the request (200 OK) without sending mail, so the bot gets no signal to adapt to. **Hide it correctly** — this is a real trap, covered in `references/troubleshooting.md`.
2. **In-memory rate limit** — cap submissions per IP within a time window. Simple, resets on cold start, good enough for a low-traffic contact form.
3. **reCAPTCHA v3** — see the dedicated reference.

## Validate and escape before sending

Coerce every field to string, trim, and bound the length server-side — the frontend's own validation is not a security boundary. Escape user input before interpolating into the HTML email body (a simple `&`/`<`/`>`/`"`/`'` replace is sufficient — see the template) so a submission can't inject markup into the email the user reads in their inbox.

## Test the backend before wiring the frontend

```bash
curl -X POST https://<project>.web.app/api/contact \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","contact":"test@example.com","message":"hello"}'
```

This isolates backend problems (secrets not set, wrong region, mail auth failing) from frontend problems (reCAPTCHA token not attached, wrong endpoint) before they get tangled together. Once reCAPTCHA is added in Phase 5, this same request will correctly get rejected with 403 (no valid token) — that's expected, not a regression.
