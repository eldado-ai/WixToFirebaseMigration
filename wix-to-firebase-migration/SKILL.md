---
name: wix-to-firebase-migration
description: End-to-end migration of an existing Wix website to self-hosted Firebase Hosting — content extraction, static site rebuild, contact-form backend as a Cloud Function, reCAPTCHA, custom domain and DNS cutover, SEO-preserving redirects, and optional Cloudflare protection. Use this skill whenever someone wants to move, migrate, escape, export, or get off Wix; wants to self-host a site currently on Wix; mentions Wix together with Firebase, Google Cloud, or static hosting; asks how to keep their domain/SEO when leaving Wix; or is midway through such a migration and needs the next step. Also use it for the sub-tasks it covers, such as extracting all blog posts out of a Wix site, replacing a Wix contact form with a real backend, or pointing a Wix-registered domain at Firebase.
---

# Wix -> Firebase migration

Wix is a closed platform: the HTML it serves is generated, the content lives behind its CMS, and the domain (if registered through Wix) is locked down in ways that block common infrastructure choices. Migrating off it means rebuilding the site as files you own, standing up replacements for the platform features the user relied on (forms, spam protection), and then moving the domain — in that order, because the domain move is the only irreversible part.

This skill sequences that work so nothing goes live before it's been proven, and so the user always knows where they are.

## Operating principles

**The old site stays up until the new one is verified.** Every phase before the cutover happens against Firebase's free `*.web.app` domain. The live site keeps serving from Wix the entire time. This is what makes the migration safe to do incrementally, over days if needed.

**Confirm before anything irreversible.** Three actions in this workflow cannot be undone easily: transferring the domain away from Wix (locks it for 60 days), deleting DNS records (brief downtime if wrong), and the DNS cutover itself. State plainly what will happen and get explicit agreement before each. Never batch these with other work.

**Report position continuously.** The user asked for a long, multi-session process; they will lose the thread if you don't hold it for them. At every phase boundary, print a status block (format below). Inside a phase, say what you're doing before a long-running step.

**Verify claims against the live system, not the deploy log.** Firebase's deploy output is not proof the change is serving — see `references/troubleshooting.md` for why this bites specifically here. `curl` the real URL and grep for the thing you changed.

## Progress reporting format

At each phase boundary, print exactly this shape so the user can scan it:

```
=== Phase 3 of 9: Firebase project setup ===
✅ Done: content extracted (44 pages), site built locally
🔄 Now:  creating Firebase project, first deploy to *.web.app
⏭️  Next: contact form backend
🌐 Live site: still on Wix, untouched
```

The `Live site` line matters most — it's the user's anxiety, and it should read "still on Wix, untouched" for the first seven phases.

## The phases

Work through these in order. Phases 8–9 are optional and often happen days later.

| # | Phase | Risk | Reference |
|---|-------|------|-----------|
| 0 | Discovery — inventory the Wix site | none | below |
| 1 | Content extraction | none | `references/content-extraction.md` |
| 2 | Site rebuild | none | below |
| 3 | Firebase setup + first deploy | none | `references/firebase-setup.md` |
| 4 | Contact form backend | none | `references/contact-form.md` |
| 5 | Spam protection (reCAPTCHA) | none | `references/recaptcha.md` |
| 6 | SEO preparation | none | `references/seo-checklist.md` |
| 7 | **Domain cutover** | **irreversible** | `references/domain-dns.md` |
| 8 | Post-cutover verification | none | `references/seo-checklist.md` |
| 9 | Cloudflare protection (optional) | needs registrar transfer | `references/cloudflare.md` |

---

## Phase 0 — Discovery

Establish what actually exists before planning anything. Ask the user for the Wix site URL, then determine:

- **Page inventory.** Fetch `https://<domain>/sitemap.xml`. Wix splits this into sub-sitemaps; follow every one. Do not infer the page list by browsing the site — see the warning in Phase 1.
- **Domain registrar.** Is the domain registered *through* Wix, or registered elsewhere and merely pointed at Wix? This determines whether Cloudflare is possible without a transfer, and changes Phase 7 substantially. Check Wix dashboard -> Domains.
- **Email on the domain.** If there are `MX` records, note every one of them plus any `TXT`/SPF/DKIM. These must survive the cutover or the user's email breaks. This is the single most damaging thing to get wrong.
- **Wix features in use.** Forms, blog, booking, store, members area. Forms and blog are covered by this skill; booking/store/members need a separate plan — say so early rather than discovering it at Phase 7.

Then ask the two questions that shape everything downstream:

1. **Design:** replicate the current Wix look as closely as practical, or rebuild fresh? Ask this explicitly, every time — never assume. Replicating suits users happy with their brand who just want off the platform. Rebuilding suits users treating the move as a redesign. If replicating, capture screenshots of every page type and note fonts/colors before you start; Wix's own CSS is machine-generated and not worth importing.
2. **Contact form:** does the site need one? If yes, Phase 4 applies and the project will need Firebase's Blaze plan.

End Phase 0 with a written plan the user agrees to: page count, design direction, feature list, and which phases apply.

---

## Phase 1 — Content extraction

Full detail in `references/content-extraction.md`. Two things determine success:

**Get the page list from the sitemap, never from the site's own navigation.** A Wix blog listing page shows a paginated or partial subset — often a handful of recent posts. The sitemap has all of them. Sites routinely have 10x more posts than the blog page suggests. Getting this wrong means silently dropping most of the user's content, and it won't be obvious until much later.

**Wix renders content with JavaScript, so `curl` returns a shell, not the article.** Use browser automation to load each URL and extract the rendered text. `curl` is still useful for the sitemap itself (plain XML) and for checking `og:` meta tags, which Wix does put in the initial HTML — but the `og:description` is truncated and is not a substitute for the body.

Store extracted content as structured data (one record per page: slug, title, category, body paragraphs), not as finished HTML. Keeping content separate from presentation means Phase 2 can regenerate all pages after any template change — which will happen, repeatedly.

Report the count when done: "Extracted 44 posts + 5 static pages." Have the user sanity-check the number against their own sense of the site.

---

## Phase 2 — Site rebuild

Build static HTML/CSS. No framework, no build step — these sites are content, not applications, and a build step adds failure modes for no benefit.

Generate pages from the Phase 1 data via a script rather than writing each by hand. With dozens of pages, hand-editing guarantees drift between them. The script owns one template; every page comes out of it. When the user requests a change to the nav, footer, or any shared element, change the template and regenerate — never patch pages individually.

Design considerations that consistently matter for sites coming off Wix:

- **Right-to-left languages.** If the content is Hebrew, Arabic, Farsi, etc., set `dir="rtl"` and test every layout at mobile width. RTL bugs hide in flexbox `justify-content`, `margin`/`padding` shorthands, and anything positioned with `left`/`right` instead of logical properties.
- **Mobile.** Wix handles this automatically; your rebuild does not. Test at 375px, not just at desktop widths. See the horizontal-overflow trap in `references/troubleshooting.md` — it's easy to introduce and hard to spot.
- **Both color schemes.** If you define CSS custom properties for a dark mode, define the complete palette at `:root` too, or the page renders one theme's text on the other's background.

Serve locally and check every page type before moving on.

---

## Phase 3 — Firebase setup and first deploy

Full detail in `references/firebase-setup.md`.

The user creates the Firebase project (account creation and billing are theirs). You then wire up `firebase.json`, deploy, and hand back the `*.web.app` URL.

If a contact form is in scope, the project needs the **Blaze (pay-as-you-go)** plan — Cloud Functions and Secret Manager are unavailable on the free Spark plan. Blaze has a free tier that a brochure site stays inside; explain that rather than letting "pay-as-you-go" alarm the user. Plan changes take a minute to propagate; if a `functions:secrets:set` command still reports a plan error immediately after upgrading, wait and retry before debugging anything else.

This phase ends with the whole site viewable at `https://<project>.web.app`. Have the user click through it properly — this is the natural review point, and finding problems here costs nothing.

---

## Phase 4 — Contact form backend

Full detail in `references/contact-form.md`. A template implementation is in `assets/functions-template/`.

Wix's built-in form disappears with Wix. The replacement is a Cloud Function that receives a POST and sends mail. Prefer this over a third-party form service when the site handles anything sensitive — a therapy practice, a clinic, a legal service — because it keeps submissions inside one provider's infrastructure instead of introducing another data processor. Say this reasoning out loud so the user can decide.

Non-obvious requirements:

- **Region.** Set it explicitly (e.g. `europe-west3` for EU data residency). The default is US.
- **Secrets.** Mail credentials go in Firebase Secret Manager via `defineSecret`, never in the source. Pipe values in without echoing them: `printf '%s' '<value>' | firebase functions:secrets:set NAME --data-file=-`.
- **Gmail app password**, not the account password, if sending via Gmail.
- **Hosting rewrite.** Route `/api/contact` to the function in `firebase.json` so the form posts same-origin and CORS never enters the picture.

Test with `curl` before wiring the frontend — it isolates backend failures from frontend ones.

---

## Phase 5 — Spam protection

Full detail in `references/recaptcha.md`.

Layer three cheap defenses rather than relying on one: a honeypot field, a per-IP rate limit, and reCAPTCHA v3.

The honeypot must be hidden with the clip technique, **not** `left:-9999px` — the off-screen approach expands the document's scroll width to ~10,000px, which breaks the layout on every phone. This is a real trap; see `references/troubleshooting.md`.

reCAPTCHA has two failure modes that look like bugs in your code and aren't:

- `Invalid domain for site key` — every domain that serves the form must be registered on the key, including `*.web.app` and `*.firebaseapp.com` during testing.
- Silent `browser-error` on verification — usually an Enterprise-type key being verified against the classic `siteverify` endpoint. Create a standard v3 key from the classic reCAPTCHA admin console.

---

## Phase 6 — SEO preparation

Full detail in `references/seo-checklist.md`. Do this **before** the cutover so search visibility transfers the moment DNS moves.

Four things, all easy to forget:

1. **Canonical and OpenGraph URLs must use the final domain**, not `*.web.app`. Pages built during Phases 2–3 will have the temporary domain baked in. Sweep every file.
2. **`sitemap.xml` and `robots.txt`** — Firebase serves neither by default.
3. **301 redirects from every old Wix URL.** Wix uses `/post/<slug>`; your rebuild will use something else. Without redirects, every indexed link 404s and the accumulated ranking is lost. Generate these from the Phase 1 data so the mapping is exhaustive.
4. **Non-ASCII redirect paths must be written raw in `firebase.json`**, not percent-encoded. Percent-encoded sources silently fail to match. Firebase handles the encoding.

Verify each redirect actually returns 301 before the cutover.

---

## Phase 7 — Domain cutover ⚠️

Full detail in `references/domain-dns.md`. **This is the irreversible phase.** Walk the user through what will happen and get explicit confirmation before touching DNS.

Order matters, and this order specifically avoids downtime:

1. Add the custom domain in Firebase Hosting **while the old DNS is still live and pointing at Wix**. Firebase issues a TXT record for ownership verification; that check needs the current DNS to be reachable. Doing this first avoids a chicken-and-egg stall later.
2. Add the TXT record in Wix's DNS. Verify in Firebase.
3. Firebase then shows the A record(s) to point at. **Add the new A record before deleting the old ones** — never leave the domain pointing at nothing.
4. Delete the old Wix A records.
5. Point `www` at the site too. Firebase can own the redirect: add `www.<domain>` as a second custom domain configured to redirect to the apex.
6. Wait for Firebase to move the domain through "Needs setup" -> "Certificate provisioning" -> **Connected**. Usually a few hours; occasionally 24.

Wix will show a "your domain points away from Wix" warning after step 4. That is the goal, not a problem — tell the user so they don't try to "fix" it.

Expect DNS caching to make the old site persist locally for the user well after the change is correct globally. Verify server-side with `curl` and `dig`; if those are right, the migration worked and the user needs a hard refresh or a different network. Do not start debugging based on the user's browser alone.

---

## Phase 8 — Post-cutover verification

Confirm on the real domain, not `*.web.app`:

- Apex and `www` both serve the new site over HTTPS
- A sample of old Wix URLs return 301 to the right new pages
- `sitemap.xml` and `robots.txt` resolve
- The contact form completes end-to-end and mail arrives
- Canonical tags reference the real domain

Then have the user add the property in Google Search Console and submit the sitemap — this speeds reindexing from weeks to days. Account setup is theirs to do.

If the site collects anything personal, this is also the point to add a privacy policy. Sites migrating off Wix usually inherit no policy at all, and the rebuild introduces its own processors (reCAPTCHA sets cookies; hosted fonts see visitor IPs). `assets/privacy-policy-template.html` is a starting point — it is not legal advice, and should say so.

---

## Phase 9 — Cloudflare protection (optional)

Full detail in `references/cloudflare.md`.

**If the domain is registered through Wix, this requires transferring the registration away first.** Wix does not permit custom nameservers on domains it registers, and Cloudflare needs the nameservers. The transfer locks the domain for 60 days and takes up to 7 days to complete. Establish whether the user actually wants Cloudflare badly enough to justify that before starting — Firebase Hosting already sits behind Google's CDN with DDoS protection, so this is an enhancement, not a fix.

If the domain is registered elsewhere, this is straightforward: add the site to Cloudflare, recreate DNS records, switch nameservers at the registrar, then enable the proxy.

Keep records **unproxied (grey cloud) until Firebase's certificate is issued**, then enable the orange cloud and set SSL mode to Full (strict). Proxying too early stalls certificate issuance.

---

## When the user arrives mid-migration

They will — this spans days. Orient before acting:

- `curl -sI https://<domain>` and check whether it's Wix or Firebase serving
- `firebase hosting:sites:list` and the Firebase console for custom domain status
- Whether `functions/` exists and whether secrets are set
- Whether `sitemap.xml`/`robots.txt` and redirects are in place

Then print the status block showing which phase they're in, and continue from there.

## Reference files

- `references/content-extraction.md` — sitemap discovery, JS-rendered content, structured storage
- `references/firebase-setup.md` — project, CLI, `firebase.json`, Blaze plan
- `references/contact-form.md` — Cloud Function, mail, secrets, region
- `references/recaptcha.md` — v3 setup and its two classic failure modes
- `references/domain-dns.md` — cutover order, records, propagation
- `references/cloudflare.md` — registrar transfer, DNS, proxy, security settings
- `references/seo-checklist.md` — canonicals, sitemap, redirects, Search Console
- `references/troubleshooting.md` — **read this when anything behaves oddly**; it holds the traps that cost the most time

## Scripts

Run with `--help` for usage.

- `scripts/discover_wix_pages.py` — enumerate every URL from a Wix sitemap
- `scripts/extract_wix_content.py` — extract rendered content to structured JSON
- `scripts/generate_site.py` — build static pages from extracted content + a template
- `scripts/generate_redirects.py` — old->new 301 map merged into `firebase.json`
- `scripts/generate_sitemap.py` — `sitemap.xml` and `robots.txt`
- `scripts/verify_migration.py` — post-deploy checks against the live domain
