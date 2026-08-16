# SEO preparation

Do this in Phase 6, **before** the domain cutover — the goal is for search visibility to transfer the moment DNS moves, not to patch it up afterward while the site sits unindexed. A domain migration is one of the highest-risk moments for a site's search ranking; each item below addresses a specific, common way that ranking gets lost.

## 1. Canonical and OpenGraph URLs must reference the final domain

Every page built in Phase 2 and deployed in Phase 3 was built and tested against the temporary `*.web.app` domain. If `<link rel="canonical">` and `og:url` were written using that domain (directly, or because a template variable defaulted to it), they are now actively telling Google to prefer the wrong URL — this is a canonical mismatch, and search engines take it seriously.

Sweep every file for the temporary domain and replace with the final one, in one pass, right before the cutover:

```bash
find . -name "*.html" -exec sed -i '' 's/OLD-project\.web\.app/final-domain.com/g' {} +
```

(Drop the `''` after `-i` on Linux; macOS's `sed` requires it.) Verify afterward:

```bash
grep -rl "web\.app" --include="*.html" .
```

Expect zero results. This includes any JSON-LD structured data blocks, which often duplicate the URL again separately from the `<link>` tag.

## 2. `sitemap.xml` and `robots.txt`

Firebase Hosting serves neither by default — they need to be actual files in the deployed output. `scripts/generate_sitemap.py` builds both from the same page-inventory data used to generate the site itself, so the sitemap can never drift out of sync with what pages actually exist.

`robots.txt` should simply allow everything and point at the sitemap:

```
User-agent: *
Allow: /

Sitemap: https://final-domain.com/sitemap.xml
```

## 3. 301 redirects from every old Wix URL

Wix's URL structure (commonly `/post/<slug>`) will not match whatever structure the rebuild uses. Without redirects, every link Google has indexed — and every bookmark, backlink, and old search result a real visitor might click — resolves to a 404 on the new site. The accumulated ranking those specific URLs built up is lost, and it can take weeks to rebuild under the new URLs from scratch.

Generate the full old->new mapping from the same structured data captured in Phase 1 (which is exactly why `old_slug` was captured then) — `scripts/generate_redirects.py` does this and merges the result into `firebase.json`:

```json
{
  "hosting": {
    "redirects": [
      { "source": "/post/<old-slug>", "destination": "/blog/<new-slug>.html", "type": 301 }
    ]
  }
}
```

**Write non-ASCII slugs raw in the source, not percent-encoded.** A source written as `/post/%D7%9E%D7%A9%D7%94%D7%95` will silently fail to match incoming requests even though the same URL percent-encoded looks identical in a browser's address bar — Firebase's route matcher expects the decoded form. This is easy to get backwards if generating the redirect list programmatically from URL-encoded input; decode before writing, always.

Verify every redirect actually works before the cutover, from the temporary domain:

```bash
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}\n" "https://project.web.app/post/old-slug"
# expect: 301 -> https://project.web.app/blog/new-slug.html
```

## 4. Search Console, after the cutover completes

Once Phase 7's DNS cutover is done and the domain shows Connected, have the user add the property in Google Search Console (https://search.google.com/search-console) and submit `sitemap.xml`. This is the fastest lever available for re-indexing speed — the difference between Google noticing the change on its normal crawl schedule (days to weeks) versus picking it up within a day or two. Account setup and property verification are the user's own Google account and are theirs to do; you can walk them through it step by step if they're logged in during the session.

## Verification checklist for Phase 8

After the cutover, confirm on the **real domain**, not `*.web.app` — a check against the temporary domain proves nothing about what's actually live for visitors:

- [ ] `<link rel="canonical">` and `og:url` on the homepage reference the final domain
- [ ] `sitemap.xml` returns 200 and lists every page
- [ ] `robots.txt` returns 200 and references the sitemap
- [ ] A sample of old Wix URLs (at least 3–5, spanning different page types) return 301 to the correct new page
- [ ] Search Console property added and sitemap submitted
