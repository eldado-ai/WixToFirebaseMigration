# Troubleshooting

These are traps encountered across real migrations that cost real debugging time — each one looks like a different kind of bug than it actually is. Check this file first when something behaves oddly; the fix is usually faster than a fresh investigation.

## "I deployed, but the change isn't live"

**Cause:** the CLI reported success, but the hosting release never finalized.

Firebase's deploy process has two phases that look similar in the log but are not equivalent:

```
✔  hosting[project-id]: file upload complete       ← files uploaded, NOT live yet
i  hosting[project-id]: finalizing version...
✔  hosting[project-id]: version finalized
i  hosting[project-id]: releasing new version...
✔  hosting[project-id]: release complete           ← now it's live
```

If the deploy command exits (errors elsewhere in the same command, gets interrupted, or the process is killed) after "file upload complete" but before "release complete," the new files are uploaded but never actually served — the site keeps serving whatever was live before, indefinitely, with no error surfaced anywhere. This is especially easy to hit when running `firebase deploy --only hosting,functions` together: a cosmetic, unrelated warning from the functions half (see next entry) can abort the whole command before hosting reaches its finalize step, even though every hosting-specific line printed looked successful.

**Fix:** always confirm "release complete" appears in the output. If it doesn't, rerun `firebase deploy --only hosting` on its own — isolating hosting from functions sidesteps the interaction entirely, and a clean hosting-only deploy reliably reaches finalization.

## "Deploy fails with an Artifact Registry cleanup policy error"

```
⚠  functions: No cleanup policy detected for repositories in europe-west3. This may result in a small monthly bill as container images accumulate over time.
Error: Functions successfully deployed but could not set up cleanup policy in location europe-west3.
```

This is cosmetic — the function itself deploys and works. It's also the exact error that can abort a combined `hosting,functions` deploy before hosting finalizes (previous entry). Don't spend time chasing the cleanup policy itself; just redeploy hosting on its own afterward to confirm it actually finalized.

## "The whole site looks broken/zoomed out on mobile, but fine on desktop"

**Cause:** almost always a single element with massive horizontal overflow, most commonly a spam-honeypot field hidden the naive way:

```css
/* Breaks the page: */
.honeypot { position: absolute; left: -9999px; top: -9999px; }
```

An absolutely positioned element at `-9999px` still counts toward its nearest scrolling ancestor's scrollable width — even though it's invisible, it expands the page's horizontal scroll area to roughly 10,000px. Mobile browsers respond to that by rendering the entire page zoomed out to fit, which looks like "everything is tiny and broken" with no obvious cause, because nothing is visually wrong — the overflow itself is invisible.

**Fix:** hide it with the clip technique instead, which keeps the element's box at 1x1px instead of moving it far outside the viewport:

```css
.honeypot {
  position: absolute;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0,0,0,0);
  white-space: nowrap;
  border: 0;
}
```

**To confirm this is the cause**, check actual scrollable width against viewport width — a large gap confirms it:

```js
document.documentElement.scrollWidth   // if this is ~10,000 and...
window.innerWidth                       // ...this is ~400, that's the bug
```

Then walk the DOM to find the specific offending element (any element with `getBoundingClientRect().right` far outside the viewport is a candidate) rather than guessing.

## reCAPTCHA errors

Two distinct failure modes, neither caused by application code — covered in full in `references/recaptcha.md`:

- `Invalid domain for site key` -> the current domain isn't registered on the key in the reCAPTCHA admin console.
- Silent `browser-error` from `siteverify` with no further detail -> likely an Enterprise-type key being checked against the classic verification endpoint; create a fresh standard v3 key.

## "It works when I test it, but not for real users" (DNS caching)

After the domain cutover (Phase 7) or any DNS change, `curl` and `dig` from your own machine can show the correct, updated answer while a real user's browser still shows the old site for hours. This isn't a contradiction — DNS resolvers cache independently at multiple layers (OS, router, ISP), each with its own expiry, entirely decoupled from whether the authoritative records are already correct.

**Always verify server-side first** (`curl -sI https://domain`, `dig domain`). If those are correct, the migration succeeded — the fix for the user's report is a hard refresh, a private/incognito window, or trying a different network, not further debugging on your end.

## RTL layout: text wraps and visually overlaps a fixed-height container

A flex container styled with a fixed pixel `height` (rather than `min-height`) and a text child that can wrap to more lines than that height accommodates — for instance a nav bar with a brand name that wraps to two lines on narrow phones — doesn't clip the overflow by default. Instead the extra lines render past the container's edge and visually collide with whatever's positioned right after it (a border, the next section).

**Fix:** use `min-height` instead of a fixed `height` wherever content can wrap, and specifically test at ~375px width in RTL layouts, where compressed horizontal space makes wrapping far more likely than in the LTR desktop view the layout was probably designed against first. If several sibling elements compete for space on the same row at narrow widths (e.g. a nav toggle, a CTA button, and a brand name all in one row), consider trimming secondary content (a subtitle, button label text) at that breakpoint rather than only adjusting the container height — a container that grows freely is the correct baseline fix, but a nav bar that grows to 3–4 lines tall is rarely the desired result either.

## A tab bar / pill row wraps to multiple lines on mobile instead of staying in one row

If a `flex-wrap: wrap` row of buttons has a total content width that exceeds the viewport, one or more will wrap to a new line rather than shrinking to fit — flexbox doesn't auto-shrink text content to keep siblings on one row unless every item explicitly allows shrinking below its natural width, which most button-shaped items with padding don't do gracefully.

**Fix:** rather than fighting for horizontal space with smaller fonts and margins (which has limits and degrades badly at very narrow widths), make the row horizontally scrollable instead — a standard, well-understood mobile pattern:

```css
.tab-row {
  flex-wrap: nowrap;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.tab-row::-webkit-scrollbar { display: none; }
.tab-row .tab-btn { white-space: nowrap; flex: none; }
```

This guarantees every item stays on one row regardless of total width or how many items there are, at the cost of the row scrolling instead of wrapping — which is the expected, familiar behavior for a tab bar on mobile.
