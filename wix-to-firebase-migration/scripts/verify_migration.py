#!/usr/bin/env python3
"""
Post-deploy verification checks against a live domain.

Run this after any deploy that's supposed to be user-facing, and especially
right after the Phase 7 domain cutover -- it catches the most common ways
a migration silently doesn't-quite-work: stale canonical URLs, a missing
sitemap, redirects that don't fire, and a hosting release that uploaded
but never finalized (see references/troubleshooting.md).

Usage:
    python verify_migration.py https://example.com
    python verify_migration.py https://example.com --redirect /post/old-slug:/blog/new-slug.html
    python verify_migration.py https://example.com --contact-form-path /api/contact

Exits non-zero if any check fails, so it's safe to use in a "did this
actually work" gate rather than just eyeballing output.
"""
import argparse
import sys
import urllib.request
import urllib.error

UA = "Mozilla/5.0 (compatible; wix-to-firebase-migration-skill/1.0)"


def fetch(url: str, method: str = "GET", follow_redirects: bool = True) -> tuple[int, str, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):
            return None

    opener = (
        urllib.request.build_opener()
        if follow_redirects
        else urllib.request.build_opener(NoRedirect)
    )
    try:
        resp = opener.open(req, timeout=15)
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body, dict(e.headers or {})


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    line = f"[{status}] {label}"
    if detail:
        line += f" -- {detail}"
    print(line)
    return condition


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base_url", help="Live site root, e.g. https://example.com")
    ap.add_argument("--redirect", action="append", default=[],
                     help="old-path:new-path pair to verify, e.g. /post/x:/blog/y.html (can repeat)")
    ap.add_argument("--contact-form-path", default=None,
                     help="If set, POSTs an empty test payload and checks for a sane rejection (not a crash)")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    results = []

    print(f"Verifying {base}\n" + "=" * 60)

    status, body, headers = fetch(f"{base}/")
    results.append(check("Homepage returns 200", status == 200, f"got {status}"))

    if status == 200:
        results.append(check(
            "Canonical URL matches this domain",
            f'href="{base}/"' in body or f"href='{base}/'" in body or base in body.split('rel="canonical"')[1][:200] if 'rel="canonical"' in body else False,
            "check <link rel=\"canonical\"> manually if this fails -- string matching on raw HTML is approximate",
        ))
        results.append(check(
            "No leftover *.web.app references in homepage HTML",
            ".web.app" not in body,
            "run: grep -rl 'web.app' --include='*.html' . -- to find stale files" if ".web.app" in body else "",
        ))

    status, body, _ = fetch(f"{base}/sitemap.xml")
    results.append(check("sitemap.xml returns 200", status == 200, f"got {status}"))
    if status == 200:
        loc_count = body.count("<loc>")
        results.append(check(f"sitemap.xml has entries", loc_count > 0, f"{loc_count} <loc> tags"))

    status, body, _ = fetch(f"{base}/robots.txt")
    results.append(check("robots.txt returns 200", status == 200, f"got {status}"))
    if status == 200:
        results.append(check("robots.txt references sitemap", "sitemap" in body.lower()))

    for pair in args.redirect:
        try:
            old_path, new_path = pair.split(":", 1)
        except ValueError:
            print(f"Skipping malformed --redirect value: {pair}")
            continue
        status, _, headers = fetch(f"{base}{old_path}", follow_redirects=False)
        location = headers.get("Location", "")
        ok = status in (301, 302) and new_path in location
        results.append(check(f"Redirect {old_path}", ok, f"got {status} -> {location or '(no Location header)'}"))

    if args.contact_form_path:
        req = urllib.request.Request(
            f"{base}{args.contact_form_path}",
            data=b'{"name":"","contact":"","message":""}',
            headers={"User-Agent": UA, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        # Any deliberate rejection (400/403) proves the function is alive and validating.
        # A 500 or connection failure means something is actually broken.
        results.append(check(
            "Contact form endpoint is alive and validating input",
            status in (400, 403),
            f"got {status} (expected 400 or 403 for an empty/invalid payload)",
        ))

    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"{passed}/{total} checks passed")

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
