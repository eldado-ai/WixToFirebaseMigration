# Wix to Firebase Migration

A Claude skill that walks you end-to-end through migrating an existing Wix website off Wix and onto self-hosted Firebase Hosting - content extraction, static site rebuild, a real contact-form backend, reCAPTCHA, custom domain and DNS cutover, SEO-preserving redirects, and optional Cloudflare protection.

## What this does

Wix is a closed platform: your content lives behind its CMS, the HTML it serves is generated, and a Wix-registered domain is locked down in ways that block most other hosting choices. This skill sequences the whole move so nothing goes live before it's proven, and so you always know where you are in the process:

1. **Discovery** - inventory the existing Wix site (pages, DNS, email records, features in use)
2. **Content extraction** - pull every page from the sitemap, not just what the nav shows
3. **Site rebuild** - static HTML/CSS, either replicating the current design or a fresh rebuild (your choice, asked up front)
4. **Firebase setup** - first deploy to a free `*.web.app` URL, old site untouched
5. **Contact form backend** - a Cloud Function replacement for Wix's form
6. **Spam protection** - reCAPTCHA v3
7. **SEO preparation** - canonical URLs, sitemap, robots.txt, 301 redirect map
8. **Domain cutover** - the one irreversible step, done only after everything above is verified live on `*.web.app`
9. **Post-cutover verification**
10. **Cloudflare protection** (optional) - free-tier DNS/WAF in front of Firebase

The old site keeps serving from Wix through every phase up to the domain cutover, so the migration can happen incrementally, over as many sessions as needed, without downtime risk.

## Usage

This is a [Claude Code / Claude Agent](https://docs.claude.com/en/docs/claude-code) skill. To use it:

1. Clone or download this repository.
2. Copy the `wix-to-firebase-migration/` folder into your skills directory (e.g. `~/.claude/skills/`).
3. Start a Claude session in the project where you want the new site to live, and ask to migrate a Wix site to Firebase.

Claude will ask for your Wix site URL, confirm whether you want to replicate the existing design or rebuild it, and then work through the phases above - reporting progress at each step and pausing for explicit confirmation before anything irreversible (the domain cutover).

## Repository layout

```
wix-to-firebase-migration/
  SKILL.md                        Entry point: phase-by-phase instructions
  references/                     Detailed guidance per topic
    content-extraction.md
    firebase-setup.md
    contact-form.md
    recaptcha.md
    seo-checklist.md
    domain-dns.md
    cloudflare.md
    troubleshooting.md            Real failure modes hit during migrations, and their fixes
  scripts/                        Helper scripts used during the migration
    discover_wix_pages.py
    extract_wix_content.py
    generate_site.py
    generate_redirects.py
    generate_sitemap.py
    verify_migration.py
  assets/                         Templates used to scaffold the new site
    privacy-policy-template.html
    functions-template/           Cloud Function template for the contact form
```

## Requirements

- A Firebase project on the Blaze (pay-as-you-go) plan if the site has a contact form (needed for Cloud Functions)
- Node.js and the Firebase CLI (`npm install -g firebase-tools`)
- Python 3 for the helper scripts, with `playwright` installed for content extraction (`pip install playwright && playwright install chromium`)

## Notes

- Nothing in this skill contains site-specific data - every script and template uses generic placeholders and is meant to be run fresh against whatever Wix site you point it at.
- The domain cutover is the only step that can't be trivially undone. The skill always states this plainly and asks for confirmation before proceeding.
