# Cloudflare protection (optional)

Firebase Hosting already sits behind Google's CDN with baseline DDoS protection. Cloudflare adds a WAF, bot-fight mode, and finer-grained rate limiting on top — genuinely useful, but an enhancement, not something the migration needs to function. Confirm the user wants this specifically, especially once they understand the registrar-transfer cost below, rather than treating it as a default final step.

## The registrar blocker

Cloudflare needs to control the domain's nameservers. **If the domain is registered through Wix, Wix does not allow custom nameservers** — so getting Cloudflare requires transferring the registration to a different registrar first (Namecheap, Cloudflare Registrar itself, etc.).

That transfer:

- Locks the domain at the losing registrar for 60 days (no further transfers in that window)
- Takes up to 7 days to complete at the new registrar
- Sends an authorization/EPP code to the domain owner's email — needed to complete the transfer at the new registrar
- Requires an account (and payment) at the new registrar — this step is the user's to do; account creation and payment details are not something to handle on their behalf

None of this affects the live site. The domain keeps resolving normally on its current DNS for the entire transfer window — there's no rush and no downtime risk from waiting.

**If the domain is registered elsewhere already**, skip straight to "Add the site to Cloudflare" below.

## Sequence once nameservers can be changed

1. **Add the site to Cloudflare** (free plan). Let it auto-scan existing DNS records, then verify against what's actually live (Phase 7 already established the correct A/CNAME records — reuse that list rather than trusting the scan blindly).
2. **Recreate every DNS record in Cloudflare** — A record(s) to Firebase's target, `www` CNAME, and any `MX`/`TXT` records for email. **Set proxy status to "DNS only" (grey cloud) for all of them at this stage.**
3. **Point the registrar's nameservers at the two Cloudflare gave you.** Propagation: minutes to ~24 hours.
4. **Wait for Firebase's custom domain status to show Connected** (same certificate-provisioning wait as Phase 7). Do not proceed to step 5 before this.
5. **Only now, switch each DNS record to Proxied (orange cloud).** This is what actually routes traffic through Cloudflare.
6. **Set SSL/TLS mode to Full (strict)** in Cloudflare — this requires the valid Firebase-issued certificate from step 4, which is why the order matters.

## Why the order matters

Enabling the Cloudflare proxy before Firebase has issued its certificate is a common way to get this stuck: Firebase's automated certificate issuance needs to reach the domain directly to complete its verification challenge, and a proxy in front of it can interfere with that, leaving the certificate pending indefinitely. If a certificate seems stuck in "provisioning" for more than a day, check first whether the proxy was turned on too early.

## Baseline security settings once live

All available on Cloudflare's free plan:

| Setting | Where | Value |
|---|---|---|
| Always Use HTTPS | SSL/TLS -> Edge Certificates | On |
| Automatic HTTPS Rewrites | SSL/TLS -> Edge Certificates | On |
| Minimum TLS Version | SSL/TLS -> Edge Certificates | TLS 1.2 |
| Bot Fight Mode | Security -> Bots | On |
| WAF managed rules | Security -> WAF | On (defaults) |
| Security Level | Security -> Settings | Medium |

Add a rate-limiting rule scoped to the contact form's API path specifically (e.g. `/api/contact`) if one is in scope — this protects the Cloud Function from being hammered, which matters because each invocation has a real (if small) cost. Pair it with a cache rule that bypasses caching on that same path, so form submissions are never inadvertently cached.

Leave **Under Attack Mode** and **HSTS** off by default. Under Attack Mode inserts a JS challenge page on every visit — reserve it for when the site is actually under attack, not as a standing setting. HSTS is close to irreversible in practice once real visitors' browsers cache it (they'll refuse to load the site over plain HTTP for the cached duration, even if HSTS is later disabled) — worth adding only after the setup has been stable for a couple of weeks, not on day one.
