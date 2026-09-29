# Copilot instructions for Benkum Art

## Project overview

This repository is a static art portfolio/site for Benkum Art. It is not a framework app or a Node/React build; it is a set of standalone HTML pages with embedded CSS and JavaScript.

The main site structure is:
- `/index.html` — homepage/gallery landing page
- `/about/index.html` — about page
- `/art/<slug>/index.html` — individual artwork/story pages
- `/assets/` — shared images, styling assets, brand media
- `/rights.html` — rights/usage page

Most changes are visual/content edits in HTML files rather than library code or component files.

## Build, test, and lint

There is no configured package manager, build system, test runner, or linter in this repository.

Use the repo as a static site:
- From the repository root, preview locally with:
  - `python -m http.server 8000`
- Then open:
  - `http://localhost:8000/`

There are no automated tests to run. For validation, do a manual browser smoke check for the page you changed: load the page, confirm the layout still renders, confirm links work, and confirm artwork images and metadata display correctly.

If you are making a content update, prefer checking the exact page you changed rather than running a broad suite (there is no suite to run).

## High-level architecture

The site is organized around static pages and a content model driven by HTML + inline scripts:

- The homepage (`/index.html`) is a gallery with a curated list of artwork entries. The entry metadata (`id`, `image`, `gridImage`, `title`, `caption`, `alt`, `glyph`, `width`, `height`, optional `next`, optional `etsyUrl`, `story`) is stored in a JavaScript array named `ARTWORKS`, oldest first.
- The gallery render logic builds the cards dynamically from that data and supports lightbox zooming, image fade-in, and "spread" paging ("Earlier work" / "Newer work"): `galleryPages()` groups pieces so a portrait sits beside two stacked landscapes (alternating sides), landscapes otherwise form a 2x2 grid, and two portraits together sit side by side. Never leave a single piece alone on a half-empty page.
- `next` is an optional, curated editorial pairing (a single "Continue →" link). There is no previous link, and next never follows array or release order.
- Each artwork page under `/art/<slug>/index.html` is a standalone HTML page containing a story page template and SEO metadata specific to that piece.
- Styling is embedded in each page rather than split into separate CSS files; the design is driven by a consistent dark palette, serif typography, gold accents, and a systematic page layout.
- The site uses a strong editorial tone: short one-line captions and short stories (about 90 words, never more than about 110) are part of the work, not decoration.

When adding or editing a piece, treat it as data + page + assets together. For a new piece, all of these are required:
- images: a watermarked `/assets/art/<slug>.jpg` master (with the small KA mark in the lower-right corner, like every other piece) and a `/assets/art/<slug>.webp` grid image (1000 px on the long side). Never ship a large PNG. Never crop, rotate, or change an artwork's orientation.
- data: a new `ARTWORKS` entry with both `image` (.jpg) and `gridImage` (.webp) and the correct `width`/`height`.
- page: `/art/<slug>/index.html` built from the most recent piece page, with the image `srcset` (webp + jpg), and a static glyph SVG that is byte-identical to what `glyphSVG(item.glyph)` renders in the browser.
- metadata: the same title/description pattern as the other pieces — `<title>` "<Title> — a piece on <subject> | Benkum Art", meta description "<caption> A piece and story about <subject>.", `og:title` "<Title> — Benkum Art", `og:description` = caption, JSON-LD `description` = meta description, `og:image` = the .jpg.
- sitemap: one `<url>` with a single `<image:image><image:loc>…jpg</image:loc></image:image>`, matching the other entries.
- homepage: update the static crawler block inside `<main id="view-root">` so it matches exactly what `galleryPages()` renders as page 1.
- typography: curly apostrophes and quotes (’ “ ”) in titles, captions, stories, and metadata.
- keep alt text, title, caption, and story copy aligned with the visual

## Key conventions

- This repo favors plain HTML over componentized JS frameworks. Do not introduce a framework unless the repository already has a clear build system for it.
- Use relative root paths like `/assets/...` and `/art/...` when linking to site assets and pages.
- Keep metadata consistent: page `<title>`, meta description, canonical URL, Open Graph tags, and JSON-LD all reflect the current piece or page.
- Follow the existing visual language: dark background, warm off-white body text, gold accent lines, and editorial serif typography.
- The gallery signals are intentionally custom: the lightbox, image fade-in, and “marked” artwork frames are part of the site’s design pattern, not random one-off effects.
- Preserve accessibility patterns already in use: `alt` text on images, visible focus styles, semantic headings, and keyboard-accessible buttons/links.
- When creating new artwork entries, keep the page and story copy in the same editorial voice as the existing collection.
- Do not assume a local build step exists; static file changes are usually verified by opening the page directly or via a local HTTP server.

## Practical editing guidance

- Prefer surgical edits in the exact HTML file you are changing.
- Do not add new frameworks, build tooling, or package dependencies without a clear reason.
- If you need to add an artwork page, mirror the structure and metadata conventions used by the existing pages under `/art/*/index.html`.
- Keep design changes consistent with the site-wide styles already embedded in the page templates.
- If a page contains both the layout and the data for the page, edit the relevant section without reformatting unrelated code.

## Related repository notes

- This file is the repository's only AI/contributor instruction file.
- There are no automated lint/test commands or package scripts to follow.
- The repo is content-first and static-first; the most important quality checks are visual and editorial correctness.

## Benkum Art project rules

- Preserve the existing Benkum Art identity and the quiet, gallery-like, editorial character of the site.
- Treat artwork titles, captions, stories, images, glyphs, and the About poem as artist-authored source material. Do not rewrite, reinterpret, summarize, "improve," correct, or replace them unless explicitly instructed.
- Do not change artwork titles, captions, stories, images, glyphs, or their ordering without explicit approval.
- Never delete an existing artwork, story, page, or asset without explicit approval.
- When a task concerns one feature, artwork, page, or component, make the smallest targeted change necessary. Do not use the task as an opportunity to redesign or refactor unrelated parts of the site.
- On this website, do not add AI-related labels, tags, disclosures, or explanatory language unless explicitly instructed. (This rule covers the website only. Etsy listings are a separate channel and must carry the artist's AI disclosure line, as Etsy requires.)
- Do not add artwork sequence numbers, release order, publishing cadence, dates, or country labels to visible page content. The one approved exception is the SEO pattern above: a piece's `<title>`, meta description, and JSON-LD description may name the real event's subject and place, as all existing pieces do.
- Do not explain the meaning or symbolism of the name "Benkum," the site's gold accent, the chalk texture, artwork glyphs, or other intentionally unexplained elements unless explicitly instructed.
- Do not add interpretations explaining what an artwork "means" unless explicitly requested. The artwork, caption, story, and associated symbols should leave interpretive space for the audience.
- Preserve the existing dark charcoal, warm off-white, restrained gold, serif/editorial visual language. Do not introduce additional brand colors or generic ecommerce styling without explicit approval.
- Preserve existing URLs, routing, metadata, structured data, responsive behavior, accessibility behavior, lightbox behavior, gallery behavior, and image-loading behavior unless the requested task specifically requires changing them. In particular, never change `galleryPages()` or the spread layout as a side effect of adding a piece; if a new piece seems to need it, stop and ask.
- Commerce stays quiet: "shop" in the site nav looks exactly like the other nav links (no accent color), and each artwork page has at most one shop link, inside the signup block — "Shop this print →" to its verified Etsy listing when the piece has an `etsyUrl`, otherwise "Shop prints →" to the shop.
- Stories follow the established shape: a short opening image, one sourced factual paragraph, and a short closing image. Quotes are verbatim; facts are sourced. The first story line never repeats the caption. Propose story edits to the artist; never rewrite them silently.
- Test every change at phone widths (360px and 375px) as well as desktop: nothing in the header may overflow.
- Never commit or push without the artist's explicit approval.
- Do not introduce frameworks, build systems, packages, dependencies, or major architectural changes unless explicitly approved.
- For commerce-related work, never invent product specifications, materials, availability, prices, fulfillment details, Etsy listing URLs, shipping claims, edition information, or quality claims. Use only verified information.
- Treat external sales channels and direct artist acquisition as separate concepts unless explicitly instructed otherwise.
- Before substantial or multi-file changes, explain what files and behaviors will be affected and wait for approval when requested.
- After changes, report exactly which files were modified and summarize what changed in each.
- If you notice an unrelated problem or improvement opportunity, report it separately rather than changing it.
- When uncertain whether a requested change conflicts with an existing Benkum Art rule or artist-authored content, ask before changing it.
