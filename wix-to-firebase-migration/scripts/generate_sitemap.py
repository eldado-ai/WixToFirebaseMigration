#!/usr/bin/env python3
"""
Generate sitemap.xml and robots.txt for the migrated site.

Firebase Hosting serves neither by default -- they need to be real files
in the deployed output. Built from the same content JSON used to generate
the site itself, so the sitemap can't drift out of sync with what pages
actually exist.

Usage:
    python generate_sitemap.py content.json --base-url https://example.com \\
        -o output_dir/ --extra-page / --extra-page /blog/index.html
"""
import argparse
import datetime
import json
import os


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("content_json", help="Structured content JSON (array of page objects)")
    ap.add_argument("--base-url", required=True, help="Final site domain, e.g. https://example.com")
    ap.add_argument("-o", "--output-dir", required=True)
    ap.add_argument("--slug-field", default="new_slug")
    ap.add_argument("--path-template", default="/blog/{slug}.html")
    ap.add_argument("--extra-page", action="append", default=[],
                     help="Additional path to include (e.g. / or /blog/index.html), can repeat")
    ap.add_argument("--priority", default="0.6", help="Priority for content pages (default: 0.6)")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")

    with open(args.content_json, encoding="utf-8") as f:
        items = json.load(f)

    today = datetime.date.today().isoformat()
    urls = []

    for extra in args.extra_page:
        path = extra if extra.startswith("/") else f"/{extra}"
        priority = "1.0" if path == "/" else "0.8"
        urls.append((f"{base}{path}", priority))

    for item in items:
        slug = item.get(args.slug_field)
        if not slug:
            continue
        path = args.path_template.format(slug=slug)
        urls.append((f"{base}{path}", args.priority))

    os.makedirs(args.output_dir, exist_ok=True)

    sitemap_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, priority in urls:
        sitemap_lines += [
            "  <url>",
            f"    <loc>{url}</loc>",
            f"    <lastmod>{today}</lastmod>",
            f"    <priority>{priority}</priority>",
            "  </url>",
        ]
    sitemap_lines.append("</urlset>")

    sitemap_path = os.path.join(args.output_dir, "sitemap.xml")
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sitemap_lines) + "\n")

    robots_path = os.path.join(args.output_dir, "robots.txt")
    with open(robots_path, "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n")

    print(f"Wrote {sitemap_path} ({len(urls)} URLs)")
    print(f"Wrote {robots_path}")


if __name__ == "__main__":
    main()
