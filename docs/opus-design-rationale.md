# Between: Opus redesign rationale

## Direction
The owner rejected the warm, wordy journal style. This version is bright, uses few words and makes the next step obvious. It uses a "sticker" visual language: ink outlines, hard offset shadows, pill controls and flat sunny colour blocks. There are no gradients-and-glass cards, stock photos, brown or serif italics.

| Token | Value | Use |
|---|---|---|
| `--ink` | #16123A | Text, outlines, shadows |
| `--petrol` | #4B2FE0 (violet) | Primary actions, links, about 7:1 contrast on white |
| `--clay` | #C42E24 | Small accent labels, about 5.6:1 contrast |
| `--sand` | #EEEBFF (lilac) | Guidance column |
| Accents | sun #FFC93C, pink #FF8AC9, mint #3DDBB0, sky #7CC8FF, coral #FF6B5B | Always behind ink text, never as the text colour |

Type is Source Sans 3 only, mostly at weight 700 with tight tracking for headings. The serif is not used.

## Homepage (`static/opus-home.js`)
1. **Hero.** A big headline with "between" set on a tilted yellow sticker. It has one sentence of supporting text, the primary CTA (`ctx.ctaLabel` linking to `#assessment`) and a secondary "Get support" link. It also shows a draft/submission status chip and three small fact chips.
2. **The Between Slider (centrepiece).** A native `<input type=range>` moves an SVG scene from *online* to *offline*. At the online end you see a phone with a scrolling feed and chat bubbles. As you slide, the phone tips over onto the grass, the sun comes up and friends walk in. Three buttons (Online / Between / Offline) jump to set points. A live caption gives a short line for each state. Both ends are shown as normal parts of life, and the copy makes no claim of effect. The note under it says "Nothing here is saved or sent". It is browser-memory only, with no storage and no network requests.
3. **How it works.** Three tilted colour tiles, plus an honest footnote that wellbeing questionnaires are switched off.
4. **"We never".** A dark band with three crossed-out icons: log into accounts, read messages, track your phone. It links to `#privacy`.
5. **Support and Study.** A coral support card that keeps the "not monitored / emergency services" line, and a sky-blue study card that links to `#about`.

## Refinement pass (after browser QA)
- **Headline.** "Life happens / between / the scrolls." is now three block-level phrases, so "between" no longer runs into "the" at any width. The phrases are separated by real spaces, so screen readers and copy/paste still get one sentence. The phrases aren't forced to `nowrap`, so large text zoom wraps a phrase instead of overflowing the page.
- **Restraint.** The sticker treatment (thick ink outline, hard shadow, tilt) is now kept for the slider stage, the highlighted word and the primary button. The How-it-works tiles are level, use softer tints and a 2px outline, and have no shadow. The support and study cards use a lighter 2px outline and a 4px shadow.
- **Offline scene.** The sun's halo is now a pale-yellow glow behind the sun. Before, it was a translucent ring that turned grey-teal over the sky. Two clouds drift in over the empty upper-left sky, and the ball has moved so it no longer touches the resting phone.

## Accessibility
- The slider is a labelled native control with `aria-valuetext` and an `aria-live` caption. The SVG is `aria-hidden`.
- The jump buttons use `aria-pressed`. All targets are at least 44px.
- Focus is shown as an ink outline plus a sun-yellow halo; on dark surfaces the outline is yellow.
- With reduced motion, the feed animation stops, the jump buttons snap instead of gliding and button hover offsets are removed.
- The in-page "What we never do" link calls `preventDefault`, then scrolls and focuses the heading.
- When printing, the decorative scene, number badges and shadows are removed. The base print rules are not changed.

## Shared app (`static/opus-theme.css`)
- **Header.** One compact grid row (brand · pill nav · actions). Below 1200px it uses two rows: brand and actions on the first, nav on the second. It never uses three rows. Below 768px the participant header hides its duplicate "Get support" pill, because Support is already in the nav and in the hero. Study access or Sign out stays next to the brand. The staff header keeps Menu and Sign out on the brand row (base CSS already hides its Get support at this width). All four nav links share the second row and are sized to fit 280px of content width at 320px. The nav has no horizontal scroller, and every target is 44px.
- **Demo strip.** Sun yellow with an ink "DEMO WORKSPACE" badge, so it can't be missed.
- **Other components restyled:** buttons, forms, choices (checked = lilac + ink outline + offset), progress bars, tags (pill + text, never colour alone), notices, error summary, panels, guidance, auth, dialog, tables, staff rail (ink, with a violet active item; collapse below 1200px is unchanged from the base CSS) and footer.
- The warm photographs that `main()` injects (`.field-page-photo`, `.access-photo`) are hidden by CSS.
