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

- The homepage (`/index.html`) is a gallery with a curated list of artwork entries. The entry metadata (id, title, caption, alt text, image paths, story text, next/previous links) is stored in a JavaScript array named `ARTWORKS` near the bottom of the file.
- The gallery render logic builds the cards dynamically from that data and supports behaviors like lightbox zooming, image fade-in, and “load more” pagination.
- Each artwork page under `/art/<slug>/index.html` is a standalone HTML page containing a story page template and SEO metadata specific to that piece.
- Styling is embedded in each page rather than split into separate CSS files; the design is driven by a consistent dark palette, serif typography, gold accents, and a systematic page layout.
- The site uses a strong editorial/art-history tone: long-form captions and art stories are part of the product, not just decoration.

When adding or editing a piece, treat it as data + page + assets together:
- update the artwork record in `/index.html` when relevant
- add or update the standalone page under `/art/<slug>/index.html`
- add the corresponding image files in `/assets/art/` (or update existing ones)
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

- There are no existing AI instruction files or repo-level contributor conventions in this repository.
- There are no automated lint/test commands or package scripts to follow.
- The repo is content-first and static-first; the most important quality checks are visual and editorial correctness.

## Benkum Art project rules

- Preserve the existing Benkum Art identity and the quiet, gallery-like, editorial character of the site.
- Treat artwork titles, captions, stories, images, glyphs, and the About poem as artist-authored source material. Do not rewrite, reinterpret, summarize, "improve," correct, or replace them unless explicitly instructed.
- Do not change artwork titles, captions, stories, images, glyphs, or their ordering without explicit approval.
- Never delete an existing artwork, story, page, or asset without explicit approval.
- When a task concerns one feature, artwork, page, or component, make the smallest targeted change necessary. Do not use the task as an opportunity to redesign or refactor unrelated parts of the site.
- Do not add AI-related labels, tags, disclosures, or explanatory language unless explicitly instructed.
- Do not add country-of-origin metadata, artwork sequence numbers, release order, or publishing cadence unless explicitly instructed.
- Do not explain the meaning or symbolism of the name "Benkum," the site's gold accent, the chalk texture, artwork glyphs, or other intentionally unexplained elements unless explicitly instructed.
- Do not add interpretations explaining what an artwork "means" unless explicitly requested. The artwork, caption, story, and associated symbols should leave interpretive space for the audience.
- Preserve the existing dark charcoal, warm off-white, restrained gold, serif/editorial visual language. Do not introduce additional brand colors or generic ecommerce styling without explicit approval.
- Preserve existing URLs, routing, metadata, structured data, responsive behavior, accessibility behavior, lightbox behavior, gallery behavior, and image-loading behavior unless the requested task specifically requires changing them.
- Do not introduce frameworks, build systems, packages, dependencies, or major architectural changes unless explicitly approved.
- For commerce-related work, never invent product specifications, materials, availability, prices, fulfillment details, Etsy listing URLs, shipping claims, edition information, or quality claims. Use only verified information.
- Treat external sales channels and direct artist acquisition as separate concepts unless explicitly instructed otherwise.
- Before substantial or multi-file changes, explain what files and behaviors will be affected and wait for approval when requested.
- After changes, report exactly which files were modified and summarize what changed in each.
- If you notice an unrelated problem or improvement opportunity, report it separately rather than changing it.
- When uncertain whether a requested change conflicts with an existing Benkum Art rule or artist-authored content, ask before changing it.
