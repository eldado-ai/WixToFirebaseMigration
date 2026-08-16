#!/usr/bin/env python3
"""
Discover every page URL on a Wix site via its sitemap.

Wix's sitemap.xml is usually a sitemap *index* pointing at sub-sitemaps
(pages-sitemap.xml, blog-posts-sitemap.xml, etc.) rather than a flat list of
pages. This script follows the index one level deep and collects every
<loc> it finds, which is the only reliable way to get the true page count --
a site's own blog listing page commonly shows only a fraction of what's
actually indexed.

Usage:
    python discover_wix_pages.py https://example.com -o urls.txt
    python discover_wix_pages.py https://example.com --json -o urls.json

Requires only the standard library (urllib, xml.etree) -- no extra
dependencies needed for this step, since sitemap.xml is always plain,
static XML even on a JS-rendered site.
"""
import argparse
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
UA = "Mozilla/5.0 (compatible; wix-to-firebase-migration-skill/1.0)"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_locs(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    # Works for both <sitemapindex> and <urlset> -- both just contain <loc> tags
    # at a predictable depth once the namespace is stripped from tag matching.
    locs = []
    for loc in root.iter():
        if loc.tag.endswith("}loc") or loc.tag == "loc":
            if loc.text:
                locs.append(loc.text.strip())
    return locs


def discover(base_url: str, verbose: bool = True) -> list[str]:
    base_url = base_url.rstrip("/")
    sitemap_url = f"{base_url}/sitemap.xml"
    if verbose:
        print(f"Fetching {sitemap_url}", file=sys.stderr)

    top_level = extract_locs(fetch(sitemap_url))

    # Distinguish "this is already a flat urlset of real pages" from
    # "this is an index of sub-sitemaps" by checking whether entries end in .xml.
    sub_sitemaps = [u for u in top_level if u.endswith(".xml")]
    all_pages: list[str] = []

    if sub_sitemaps:
        if verbose:
            print(f"Found sitemap index with {len(sub_sitemaps)} sub-sitemaps", file=sys.stderr)
        for sub_url in sub_sitemaps:
            if verbose:
                print(f"  Fetching {sub_url}", file=sys.stderr)
            try:
                all_pages.extend(extract_locs(fetch(sub_url)))
            except Exception as e:
                print(f"  WARNING: failed to fetch {sub_url}: {e}", file=sys.stderr)
    else:
        all_pages = top_level

    # De-dupe while preserving order.
    seen = set()
    deduped = []
    for u in all_pages:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    if verbose:
        print(f"Total pages discovered: {len(deduped)}", file=sys.stderr)
    return deduped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base_url", help="Site root, e.g. https://example.com")
    ap.add_argument("-o", "--output", default="-", help="Output file (default: stdout)")
    ap.add_argument("--json", action="store_true", help="Output JSON array instead of one URL per line")
    args = ap.parse_args()

    urls = discover(args.base_url)

    if args.json:
        out_text = json.dumps(urls, ensure_ascii=False, indent=2)
    else:
        out_text = "\n".join(urls) + "\n"

    if args.output == "-":
        print(out_text)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_text)
        print(f"Wrote {len(urls)} URLs to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
