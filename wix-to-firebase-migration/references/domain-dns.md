# Domain cutover

This is the one phase in the whole migration that is genuinely hard to undo — DNS changes propagate outward and a mistake here means a real outage for real visitors. Everything before this point (site rebuild, function, reCAPTCHA, SEO prep) was rehearsed safely against `*.web.app`. Do not start this phase without the user's explicit go-ahead on this specific step, separate from earlier general approval to "do the migration."

## Before touching anything: check the registrar

Ask: is the domain registered *through* Wix, or registered elsewhere (Namecheap, GoDaddy, Google Domains, etc.) and just pointed at Wix's nameservers?

**If registered through Wix**, Wix does not allow setting custom nameservers on domains it registers — this blocks Cloudflare (Phase 9) entirely until the registration moves elsewhere. It does *not* block this phase: Wix's own DNS records panel can still be edited directly (Wix dashboard -> Domains -> Manage DNS Records), which is all this phase needs. Only pursue a registrar transfer if Phase 9 (Cloudflare) is actually wanted — don't do it as a default step.

**If registered elsewhere**, DNS is likely already editable through that registrar or through Wix's DNS panel for this domain, either way — confirm which one actually controls the live records before editing.

## The order that avoids downtime

Each step depends on the previous one being live. Don't skip ahead.

**1. Verify domain ownership with Firebase while the old DNS is still fully live.**

In the Firebase console: Hosting -> Add custom domain -> enter the domain. Firebase issues a TXT record for verification. This check needs to reach the domain's *current* DNS — which is still pointing at Wix — so do this before anything else changes. Add the TXT record via the DNS panel identified above, then click Verify in Firebase.

**2. Firebase then shows the A record(s) to point the domain at.** Copy these — they're specific to the project, don't assume they're the same across every Firebase project.

**3. Add the new A record(s) alongside the existing Wix ones — don't delete anything yet.** The domain briefly has both old and new A records simultaneously. This is fine; DNS clients that hit either will get a working answer.

**4. Only now, delete the old Wix A records.** This is the actual cutover moment — traffic starts landing on Firebase instead of Wix from here on, as caches expire. Confirm with the user immediately before this specific step, even if they approved the phase in general — this is the line between "everything is still reversible" and "the change is live."

**5. Point `www` at the site too, as a separate Firebase custom domain configured to redirect to the apex** (Firebase supports this natively when adding the second domain — check the redirect option rather than trying to hand-roll a CNAME to the same target). Update the DNS `CNAME` for `www` to Firebase's target once that second domain is added, using the same add-before-delete order as above.

**6. Wait for the certificate.** Firebase's custom domain status moves through "Needs setup" -> "Certificate provisioning" -> **Connected**. This typically takes minutes to a few hours, occasionally up to 24. The domain is not safe to consider "done" until it shows Connected — an uncertified domain can show browser security warnings.

## Don't lose email

If the domain has `MX` records (check in Phase 0), they must be recreated identically wherever the new DNS lives — losing them silently breaks the user's email on that domain the moment records are deleted. Recreate `MX`, and any `TXT` records used for SPF/DKIM, in the same pass as step 3, not as an afterthought.

## Expected, not a bug

**Wix shows a "your domain points away from Wix" warning after step 4.** This is Wix correctly detecting that DNS no longer resolves to it. It's the intended outcome, not something to fix — tell the user this proactively so they don't try to "repair" it back to Wix.

**The user reports the old site (or a "Site Not Found" error) still showing minutes or hours after the cutover, from their own browser.** Verify server-side first — `curl -sI https://<domain>` and `dig <domain>` — before assuming anything is actually wrong. DNS resolvers cache independently at many layers (the user's OS, their router, their ISP), and each expires on its own schedule regardless of how correct the new records are. If server-side checks are correct, tell the user to try a hard refresh, a private/incognito window, or a different network (e.g. phone on cellular data) — don't debug the "problem" further if the server side already checks out.

## After Firebase deploys during this phase

Every hosting deploy in this and later phases is subject to the release-finalization trap in `references/troubleshooting.md` — confirm "release complete" appeared, not just "file upload complete," especially right after this phase when a stale cached version would be maximally confusing to debug.
