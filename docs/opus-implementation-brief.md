# Requested collaboration: Claude Opus 5.5

The owner specifically requested Opus 5.5 after rejecting several of my designs. They say the website is just too many words and brown backgrounds, and want substantial creative product design. Your role is to DESIGN AND IMPLEMENT the replacement, not just provide advice.

Read `static/app.js`, `static/styles.css`, `static/index.html`, `design-spec.txt`, and `test-results/home-desktop.png` to understand the existing app and what was rejected. The owner's latest direction supersedes the document's palette and journal styling. Discard beige, brown, sand paper, rust italics, photo-print/polaroid styling and long text-heavy presentation. This should be an inviting, bright, visually distinctive youth digital product with a meaningful interactive centerpiece, fewer words, and immediately obvious actions. Use your strongest creative judgement. Avoid a generic gradient-and-cards AI landing page, fake metrics, a therapy chatbot, mood tracking, or diagnosis claims. The study covers ages 13–24, self-reported social-media habits; wellbeing instruments and model scoring are unavailable. The UI must remain visibly Demo.

## Your exact file ownership

Create `static/opus-home.js` and `static/opus-theme.css`. You may also create `docs/opus-design-rationale.md`. Do not edit any other files. Do not run shell commands. The parent agent handles integration, browser QA, regressions and server operation. You have Read/Write/Edit/Glob/Grep tools.

### JavaScript contract

The parent will load your script before `app.js`, as a classic deferred browser script. Define:

```js
window.renderOpusHome = function (ctx) { return '...HTML...'; };
window.initOpusHome = function () { /* attach local interaction handlers */ };
```

`ctx` supplies `ctaLabel` (Start my assessment / Continue my assessment / View my summary), `icon(name)` (returns trusted outline SVG HTML), `esc(value)` (HTML escapes untrusted values), `fmt(timestamp)`, `draft`, `submission` and `user` (null when unsigned). Use ctx.esc on dynamic data. Retain one section with class `home-main` for existing test selectors. Make the primary assessment action a real link to `#assessment` using ctx.ctaLabel, support to `#support`, privacy to `#privacy`, study details to `#about`. Keep returning draft/submission information functional. Any interactive visual must be browser-memory-only, make no network requests, collect no sensitive answers, and have no claimed mental-health effect. It needs keyboard accessibility, visible focus and reduced-motion support. Do not use localStorage, cookies, service workers, imports, frameworks, external scripts or network resources. Use native HTML/CSS/SVG/canvas/JS when suitable. You can use existing local `static/images/*.webp` but are not required to retain those warm images. Aim for a genuinely different first viewport and an interactive experience, not more paragraphs.

`app.js` already has delegated click events for specific data attributes. Do not reuse `data-action`, `data-preview`, `data-edit-step`, `data-privacy` etc for your new local interactions; use unique attributes and attach listeners in initOpusHome. Inner-page anchors must prevent the default hash routing; use scrollIntoView/focus instead. Global navigation uses location.hash and is handled by the parent app.

### CSS contract

Your CSS loads AFTER `static/styles.css`; the old `identity.css` and `field.css` will NO LONGER be loaded. Restyle the ENTIRE shared app coherently, as well as your homepage. Define new root variables --paper, --surface, --ink, --muted, --petrol, --clay, --sand, --line, --green, --amber, --red, --sans, --serif to avoid inherited brown. Fonts Source Sans 3 and Source Serif 4 are already self-hosted; use sans for a modern app, serif only if a deliberate small accent. The header markup comes from shell() in app.js: .brand-row with .brand (SVG .brand-symbol, .wordmark, .brand-period, .brand-caption), .header-actions, then .participant-nav. Make it modern and compact. Style base .page-grid, .guidance, .notice, .panel, .assessment-wrap, .progress, .choices/.choice, .form-actions, .auth-wrap, .staff-shell/.staff-nav/.staff-content and tables. Keep 320px screens without page-level horizontal scrolling, readable choices and 44px controls. Staff side rail collapses below 1200px. Preserve the print styles in base CSS and hide any decorative homepage graphics when printing. New styles must not break report printing, modal focus, errors or form validation.

Prioritise the strongest design you can actually implement in these files. Deliver finished source, not a plan. In the final response, state what you built and any integration issues. I will then send you browser screenshots for critique and revisions.
