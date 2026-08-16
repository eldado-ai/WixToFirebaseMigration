#!/usr/bin/env python3
"""
Extract rendered content from Wix pages (blog posts, static pages) into
structured JSON.

Wix pages are client-side rendered -- the article body is populated by
JavaScript after load, so a plain HTTP fetch only returns the page shell.
This script uses a headless browser (Playwright) to render each page and
pull text out of the DOM after JS has run.

If Playwright isn't available in the current environment, don't fight it --
this same extraction works fine done interactively through a browser
automation tool instead (navigate, wait for load, read rendered text),
just page-by-page instead of batched. See references/content-extraction.md.

Setup (one-time):
    pip install playwright
    playwright install chromium

Usage:
    python extract_wix_content.py urls.txt -o content.json
    python extract_wix_content.py urls.txt -o content.json --selector "article"

Input: a text file with one URL per line (output of discover_wix_pages.py).
Output: a JSON array of {url, title, meta_description, body_paragraphs}.

This intentionally does NOT invent a "new_slug" or "category" for you --
those are content decisions. Fill them in as a second pass once you've
looked at the extracted titles, or hand this file to Claude to do it in
context of the rest of the migration.
"""
import argparse
import json
import re
import sys
import time


def extract_one(page, url: str, selector: str) -> dict:
    page.goto(url, wait_until="networkidle", timeout=30000)
    # Give client-side rendering a moment to settle beyond "networkidle" --
    # Wix sometimes finishes a late render pass just after network activity quiets.
    page.wait_for_timeout(500)

    title = page.title()

    meta_description = page.evaluate(
        """() => {
            const m = document.querySelector('meta[name="description"], meta[property="og:description"]');
            return m ? m.getAttribute('content') : '';
        }"""
    )

    body_text = page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel) || document.body;
            return el.innerText || '';
        }""",
        selector,
    )

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body_text) if p.strip()]

    return {
        "url": url,
        "title": title,
        "meta_description": meta_description or "",
        "body_paragraphs": paragraphs,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls_file", help="Text file with one URL per line")
    ap.add_argument("-o", "--output", default="content.json")
    ap.add_argument("--selector", default="article", help="CSS selector for the content container (default: article)")
    ap.add_argument("--delay", type=float, default=0.3, help="Seconds to wait between page loads (default: 0.3)")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright isn't installed in this environment.\n\n"
            "Install it with:\n"
            "    pip install playwright && playwright install chromium\n\n"
            "Or skip this script and extract interactively instead, using whatever\n"
            "browser automation tool is available in this session -- navigate to each\n"
            "URL, wait for it to load, and read the rendered text. Same result, just\n"
            "one page at a time instead of batched. See references/content-extraction.md.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(args.urls_file, encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"Extracting {len(urls)} pages...", file=sys.stderr)

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for i, url in enumerate(urls, 1):
            print(f"  [{i}/{len(urls)}] {url}", file=sys.stderr)
            try:
                results.append(extract_one(page, url, args.selector))
            except Exception as e:
                print(f"    FAILED: {e}", file=sys.stderr)
                results.append({"url": url, "title": "", "meta_description": "", "body_paragraphs": [], "error": str(e)})
            time.sleep(args.delay)
        browser.close()

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    failed = sum(1 for r in results if r.get("error"))
    print(f"\nWrote {len(results)} pages to {args.output} ({failed} failed)", file=sys.stderr)
    if failed:
        print("Review failed entries -- often a slug encoding mismatch or a soft-404.", file=sys.stderr)


if __name__ == "__main__":
    main()
