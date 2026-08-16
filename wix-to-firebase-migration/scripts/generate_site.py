#!/usr/bin/env python3
"""
Generate static HTML pages from structured content JSON + one HTML template.

The core idea: keep exactly one template file with placeholder tokens, and
regenerate every page from it. When the user asks for a nav/footer/design
change, edit the template once and rerun this script -- never hand-patch
individual generated pages, which guarantees drift across dozens of files
the moment a second change request comes in.

Usage:
    python generate_site.py content.json template.html -o output_dir/ \\
        --slug-field new_slug --base-url https://example.com

Template placeholders (customize the --token-* flags if your template uses
different names):
    __TITLE__    -> content item's title
    __META__     -> meta description
    __SLUG__     -> the item's slug (for canonical/og:url construction)
    __TAG__      -> a category/tag label, if present in the content JSON
    __BODY__     -> body paragraphs, wrapped in <p> and HTML-escaped

Content JSON shape expected (one object per page):
    {
      "new_slug": "some-page",
      "title": "Page Title",
      "meta_description": "...",
      "category": "Category",             (optional)
      "body_paragraphs": ["...", "..."]
    }
"""
import argparse
import html
import json
import os
import re


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def paragraphs_to_html(paragraphs: list[str]) -> str:
    return "".join(f"<p>{esc(p)}</p>" for p in paragraphs)


def make_meta(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 3].rsplit(" ", 1)[0]
    return cut + "..."


def render(template: str, item: dict, slug_field: str, tag_field: str) -> str:
    slug = item.get(slug_field, item.get("new_slug", ""))
    title = item.get("title", "")
    body_paragraphs = item.get("body_paragraphs", [])
    meta = item.get("meta_description") or make_meta(
        body_paragraphs[0] if body_paragraphs else title
    )
    tag = item.get(tag_field, item.get("category", ""))

    out = template
    out = out.replace("__TITLE__", esc(title))
    out = out.replace("__META__", esc(meta))
    out = out.replace("__SLUG__", slug)
    out = out.replace("__TAG__", esc(tag))
    out = out.replace("__BODY__", paragraphs_to_html(body_paragraphs))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("content_json", help="Structured content JSON (array of page objects)")
    ap.add_argument("template", help="HTML template file with __TOKEN__ placeholders")
    ap.add_argument("-o", "--output-dir", required=True)
    ap.add_argument("--slug-field", default="new_slug", help="JSON field to use as the output filename (default: new_slug)")
    ap.add_argument("--tag-field", default="category", help="JSON field to use for __TAG__ (default: category)")
    args = ap.parse_args()

    with open(args.content_json, encoding="utf-8") as f:
        items = json.load(f)

    with open(args.template, encoding="utf-8") as f:
        template = f.read()

    os.makedirs(args.output_dir, exist_ok=True)

    slugs_seen = set()
    written = 0
    for item in items:
        slug = item.get(args.slug_field)
        if not slug:
            print(f"SKIPPING item with no '{args.slug_field}': {item.get('title', '(untitled)')}")
            continue
        if slug in slugs_seen:
            print(f"WARNING: duplicate slug '{slug}' -- later item overwrites earlier one")
        slugs_seen.add(slug)

        page_html = render(template, item, args.slug_field, args.tag_field)
        out_path = os.path.join(args.output_dir, f"{slug}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page_html)
        written += 1

    print(f"Wrote {written} pages to {args.output_dir}/")
    if written != len(items):
        print(f"({len(items) - written} items skipped -- see warnings above)")


if __name__ == "__main__":
    main()
