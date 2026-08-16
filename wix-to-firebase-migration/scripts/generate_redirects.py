#!/usr/bin/env python3
"""
Generate 301 redirects from old Wix URLs to new site URLs, and merge them
into firebase.json's hosting.redirects array.

Without these, every link Google has indexed to the old Wix URL structure
(commonly /post/<slug>) 404s the moment the domain cuts over, and the
ranking those specific URLs built up is lost.

IMPORTANT: sources are written RAW (decoded), not percent-encoded --
Firebase's route matcher expects the decoded form and will silently fail to
match a percent-encoded source even though it looks correct in a browser's
address bar. This script decodes automatically if it detects %-encoding.

Usage:
    python generate_redirects.py content.json firebase.json \\
        --old-url-field url --old-path-prefix /post/ \\
        --new-path-template "/blog/{slug}.html"

Content JSON shape expected (same file used by generate_site.py):
    {
      "url": "https://example.com/post/old-slug",   <- old Wix URL
      "new_slug": "new-slug"
    }
"""
import argparse
import json
import urllib.parse
from urllib.parse import urlparse


def old_path_from_url(url: str) -> str:
    path = urlparse(url).path
    # Decode in case the crawled/stored URL was percent-encoded.
    return urllib.parse.unquote(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("content_json", help="Structured content JSON with old URLs and new slugs")
    ap.add_argument("firebase_json", help="firebase.json to update in place")
    ap.add_argument("--old-url-field", default="url", help="JSON field holding the old Wix URL (default: url)")
    ap.add_argument("--new-slug-field", default="new_slug", help="JSON field holding the new slug (default: new_slug)")
    ap.add_argument("--new-path-template", default="/blog/{slug}.html",
                     help="Template for the new path, {slug} is replaced (default: /blog/{slug}.html)")
    ap.add_argument("--dry-run", action="store_true", help="Print the redirects without writing firebase.json")
    args = ap.parse_args()

    with open(args.content_json, encoding="utf-8") as f:
        items = json.load(f)

    redirects = []
    skipped = 0
    for item in items:
        old_url = item.get(args.old_url_field)
        new_slug = item.get(args.new_slug_field)
        if not old_url or not new_slug:
            skipped += 1
            continue
        source = old_path_from_url(old_url)
        destination = args.new_path_template.format(slug=new_slug)
        redirects.append({"source": source, "destination": destination, "type": 301})

    print(f"Built {len(redirects)} redirects ({skipped} items skipped for missing fields)")

    if args.dry_run:
        print(json.dumps(redirects[:3], ensure_ascii=False, indent=2))
        print(f"... and {max(0, len(redirects) - 3)} more")
        return

    with open(args.firebase_json, encoding="utf-8") as f:
        config = json.load(f)

    config.setdefault("hosting", {})["redirects"] = redirects

    with open(args.firebase_json, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"Updated {args.firebase_json} with {len(redirects)} redirects")
    print("\nVerify a few after deploying, e.g.:")
    if redirects:
        print(f'  curl -s -o /dev/null -w "%{{http_code}} -> %{{redirect_url}}\\n" "https://YOUR-DOMAIN{redirects[0]["source"]}"')


if __name__ == "__main__":
    main()
