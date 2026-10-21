# CLAUDE.md — Benkum Art

Instructions for Claude Code sessions on this repository (local or cloud). Read
`.github/copilot-instructions.md` first: its site structure, editorial rules and
"Benkum Art project rules" apply in full. This file adds how Claude works here.

The artist and repository owner is Kae (Kwame Asiedu). Refer to them by name.

## This repository is public

Some of the project's creative notes are private and are kept outside this
repository on purpose. Never add, summarize or allude to them, and never
explain or speculate about the meaning of any intentionally unexplained
element (glyphs, marks, ordering, styling), in code, comments, commits, pull
requests or site content.

## How changes ship

- `main` is protected: every change goes on its own branch and through a pull
  request. Never push to `main`, force-push it, or try to bypass the ruleset.
- CodeRabbit reviews every PR automatically. Read its comments, verify each one
  against the code, fix the valid ones (re-running any generator involved) and
  wait for a clean re-review. A green CodeRabbit status alone is not "clean":
  check that there are no actionable comments and no unresolved threads.
- Merge only after Kae's explicit OK for that PR (an OK such as "merge it once
  CodeRabbit is clean" counts for that PR only). Merge with a merge commit; the
  ruleset allows nothing else, and merged branches delete themselves.
- Before pushing, show Kae what will change (wording, screenshot, or a preview)
  unless they have already approved that specific change.
- After a merge, confirm the change is live on https://benkum.art (GitHub Pages
  builds from `main`, usually within a minute or two).
- Never publish new pieces or post to social media on your own.

## Generated parts of the site: never hand-edit

| Output | Edit this instead | Then run |
|---|---|---|
| Map + slideshow block between `<!-- MAP:START` and `<!-- MAP:END -->` in `index.html` | `tools/render_map.py`, `tools/map-pieces.json`, `tools/map-chips.json` | `python tools/render_map.py` |
| `works/index.html` (the curated Works gallery) | `tools/render_works.py` (`DESKTOP` and `PHONE` layouts) | `python tools/render_works.py` |
| `cycle-i/in-your-space/index.html` (Cycle I room viewer) | `tools/render_rooms.py`, `tools/cycle-i-rooms.json` | `python tools/render_rooms.py` (also after adding a piece) |
| `cycle-i/in-your-space/rooms/<id>-wall.png` (wall masks for the shade option) | `tools/build_wall_masks.py` (hand-traced wall areas and furniture) | `python tools/build_wall_masks.py --preview <dir>` only when a room image changes; check with a dark shade before committing |
| `assets/map/africa-geometry.json` | `tools/build_map_geometry.py` | only when the map shapes must change |

The render scripts need Python with Pillow. Commit the regenerated files with
the generator change, so the page always matches its source.

## Decisions Kae has made (keep them)

- **Cycle I map:** no visible country names, numbers, dates or release order;
  screen readers hear "Country: Title". Unfinished countries are `#2A2621`.
  Western Sahara is one separate, neutral, unlinked shape. Somaliland is drawn
  within Somalia. Island states use circular markers. Each piece's focal crop
  in `tools/map-pieces.json` is approved by Kae.
- **Map behaviour:** on desktop the card follows the pointer and can be clicked
  once the pointer rests; on phones a tap opens the piece directly. The
  homepage fits on one screen.
- **Slideshow:** no Play/Pause control anywhere. It drifts at 28 px/s, rests
  on hover, keyboard focus and touch, and can be swiped, scrolled or dragged.
- **Works:** curated by visual relationships only (never release order,
  country, title or story), with large/medium/small sizing; images only.
  The arrangement in `tools/render_works.py` is approved. Don't reorder it
  without Kae.
- **Cycles are kept apart.** Everything published so far is Cycle I. Its pages carry
  `data-cycle="i"` on `<html>`, and Cycle I-only features live under `cycle-i/`
  (the "In your space" room viewer, its rooms and data). Never move them to
  shared code or the main navigation: Cycle II will get its own style and
  system later. The header (works · about · write · follow) stays cycle-neutral.
- **In your space:** one shared viewer, opened from a quiet "See it in your
  space" link under each piece's caption and one line on the Works page. Sizes
  are illustrative 2:3 sizes at true scale (no prices, no shop wording while
  the shop is closed); rooms are labelled as visualizations. Pieces are listed
  in the Works curated order, never release order.
- **Never describe Kae with a nationality label.** Lead with their authorship.
- **The KA mark** is the upright gold-leaf KA (flat gold `#EAAE45` on
  `#141414` at small sizes), never the italic monogram.

## New pages and pieces

- Follow the new-piece checklist in `.github/copilot-instructions.md`, which
  includes the Cycle I map and Works steps.
- Every content page carries the Umami script in `<head>` (copy it from any
  existing page). The one exception is the `/ig/` forwarding page below. Etsy links carry `data-umami-event="etsy-click"` with a
  `data-umami-event-from` value (`nav`, `piece-page`, `story` or `write`), and
  `data-umami-event-piece` set to the slug where one applies.
- `benkum.art/ig` is the Instagram bio short link (`/ig/index.html`). It only
  forwards to the homepage with the Instagram tags, and it must have **no Umami
  script and no event tags**: the visit is counted once, on the homepage.

## Checking work

- Serve the repo with `python -m http.server 8000` and check desktop and phone
  widths (360, 375 and 390 px, plus desktop): no horizontal overflow, the header fits, and the
  console is clean.
- Check every artwork link opens the right `/art/<slug>/` page, and images keep
  their natural proportions.
