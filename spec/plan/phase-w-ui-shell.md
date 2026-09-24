[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase W — Post-MVP: application shell, theming, and i18n

**Why now.** Raised 2026-09-24 with a hand-drawn target layout
(`examples/ui/main_ui.png` / `.svg`, committed alongside this file): a title bar, a left sidebar
carrying a vertical step nav (Priorities / Attributes / Qualities / Skills / Magic / Resonance /
Augmentation / Equipment / Contacts / Bio / Export) with a remaining-resources panel beneath it, and
a single main pane showing the currently-selected step. The sketch is explicitly high-level
orientation — it says nothing about any individual page's contents, and this phase does not change
any step's *contents* either. What it changes is the frame around them.

The same request asked two structural questions alongside the layout, and they are folded into this
phase rather than deferred, because both are dramatically cheaper while the templates are already
open for the layout work than as a second full traversal afterwards:

- **Themability** — the graphical furniture (separators, backgrounds, fonts, the nav's own chrome)
  should be swappable without editing markup.
- **Internationalization** — not set up at all today, despite `Project Overview.md` claiming it as
  in-MVP scope. See WP102's own note.

**Finding 1 — the step fragments are already at the right granularity.** Phase R's WP62 split
`web/app.py` into one router per chargen step, and each step already renders *only* its own
`_*.html` partial into its own `<div id="...-section">` with `hx-swap="outerHTML"`. A page-per-nav-
item layout needs exactly that decomposition, and it already exists. The corollary matters for
scoping: **no step route's URL, context builder, or fragment template needs to change** to move from
an accordion to a nav — only where the fragment is mounted changes. The one exception is
`POST /ui/priorities`, which re-renders the whole `_chargen_body.html` because a priority change
invalidates every other step (see WP97's notes).

**Finding 2 — the accordion machinery is all disposable.** `ChargenSession.open_section` (WP61),
the `<details>`-per-section markup, the `⚠`-on-collapsed-`<summary>` marker (WP61), and the ~70-line
open/closed-state store in `base.html` (WP64) exist *solely* to make 15 stacked sections behave like
one-at-a-time. A sidebar nav makes the whole apparatus unnecessary — not refactored, deleted.
`open_section` survives only in the sense that its role (server-side "which step is showing") is
exactly what the nav needs; it is renamed, not reimplemented.

**Finding 3 — two of the sketch's eleven nav items have nothing behind them.**
*Resonance* has no engine support whatsoever (technomancers are out of scope — see `Project
Overview.md`'s MVP scope), and *Bio* has no data model at all: `Character` carries no name, alias,
street name, metatype description, or notes fields, so a Bio page is new engine + save-format work,
not layout work. **Both are out of this phase's scope.** WP97 renders them as visibly-disabled nav
entries rather than as empty pages or as silent omissions from the sketch. Either can become its own
later phase; neither blocks anything here.

**Finding 4 — the eleven nav items do not map 1:1 onto the fifteen current sections.** Three nav
items are composites, and that is where the only genuine design work in this phase sits:

| Nav item | Today's section(s) in `_chargen_body.html` |
|---|---|
| Priorities | `_priority_form` |
| Attributes | `_attribute_allocation` |
| Qualities | `_quality_selection` |
| Skills | `_skill_allocation` + `_knowledge_skills` |
| Magic | `_talent_selection` + `_spell_selection` + `_power_selection` + `_spirit_selection` + `_foci_selection` |
| Resonance | *(nothing — see Finding 3)* |
| Augmentation | `_cyberware` (cyberware **and** bioware — one section since WP45) |
| Equipment | `_resources` + `_vehicles` + `_lifestyle` |
| Contacts | `_contacts` |
| Bio | *(nothing — see Finding 3)* |
| Export | `character_sheet` + the save / load / import-`.chum5` routes |

**Finding 5 — no new dependency is needed, for any of the three concerns.** The shell is CSS Grid;
the pane swap is htmx, already vendored; theming is custom properties; and Jinja2 3.1.6 ships
`jinja2.ext.i18n` in the box. This is worth stating explicitly because each of the three has an
obvious "just add the standard library for it" reflex (a CSS framework, a theming toolkit, Babel) and
none of them earns its toolchain here — see `Project Overview.md`'s stack decision, and WP102's own
gettext-vs-key-layer note for the one place the call is genuinely arguable.

**Finding 6 — test exposure is much smaller than the 5,858 lines of web tests suggest.** Eighteen
test modules drive the app through `TestClient`, but nearly every one uses `client.get("/")` only to
establish a session cookie and then asserts on the fragment returned by a `POST /ui/<step>` — all of
which is untouched by Findings 1 and 2. The real casualties are `tests/unit/test_web_accordion.py`
(153 lines, entirely about the mechanism WP97 deletes) and any assertion that a *non-priorities*
section's content appears in `GET /`, which after WP97 it no longer does.

**Sequencing.** WP97 → WP98 are the load-bearing pair and should land in order. WP99 wants WP97's
shell to hang off. WP100 is separable but must not be *skipped ahead of* WP97/98 — its Notes explain
the one constraint those two WPs have to honour for it to stay cheap. WP101 → WP102 → WP103 are the
i18n chain; WP101 can land any time, but WP102 is much cheaper folded into WP97/98's own template
edits than run afterwards, so prefer WP101 *before* WP97 if the context budget allows it.

---

- [ ] **WP97 — The application shell: title bar, step nav, content pane.**
  Goal: replace the single-page accordion with the sketch's three-area frame, and move the six 1:1
  steps (Priorities, Attributes, Qualities, Contacts, Augmentation, Export) into it unchanged.
  Deliverables:
  - `base.html` becomes a genuine shell: a CSS Grid with a title-bar row and a sidebar/main row.
    The sidebar holds the step nav (and, from WP99, the resource panel); the main area is a single
    `<div id="page">` swap target. The ~70-line `<details>`-state script (WP64) and the `⚠`-on-
    collapsed-`<summary>` markers (WP61) are **deleted**, not ported.
  - A nav route — `GET /ui/page/{slug}` — returning that step's fragment, driven from the nav with
    `hx-target="#page"` plus `hx-push-url` so the browser's back button walks the step history. A
    direct `GET` of a page URL must render the full shell with that step selected, not a bare
    fragment (a bookmarked or reloaded step URL has to work).
  - `ChargenSession.open_section` → `current_page`, holding a nav slug rather than a section div id;
    each step's successful `POST` sets it to its own slug, exactly as `open_section` already worked.
  - `_chargen_body.html` retires. `GET /` redirects to (or renders) the Priorities page.
  - Resonance and Bio render as disabled nav entries — present, visibly unavailable, not clickable
    (Finding 3).
  - `tests/unit/test_web_accordion.py` is rewritten as `test_web_shell.py`: nav renders all eleven
    entries with the right two disabled, the current step is marked, a page `GET` returns that step
    and only that step, a step `POST` leaves `current_page` on that step, and a direct page-URL
    `GET` returns the full shell.
  Notes and traps: `POST /ui/priorities` is the one route that renders more than its own fragment —
  a priorities change re-validates every other step's carried-forward selections (WP19), so it
  currently re-renders all fifteen. Under the shell it should re-render the *priorities page* and
  refresh the resource panel out-of-band (WP99), **not** attempt to re-render steps that aren't on
  screen; the WP19 "no longer fits" warnings still have to reach the player, so carry them as a
  per-step marker on the nav itself rather than losing them. Check `_chargen_body_context`'s
  `priority_stale_selections` aggregate (`routes/priorities.py`) — it already computes exactly the
  per-step staleness a nav marker needs, so this is a re-render of existing information, not new
  logic. Second trap: several step templates run client-side filter scripts whose state is restored
  across htmx swaps (WP64, WP83); those scripts live *inside* the swapped fragment and keep working
  unchanged, but any store they hang on `window` must survive a **page** swap too, not just a
  section swap — check each one rather than assuming.
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` green; no step route's URL changed; `grep -c '<details'` over
  the six moved templates is unchanged (this WP does not restructure any step's *contents*); a
  priorities change that invalidates a committed skill spend still surfaces that warning to the
  player without the Skills page being open.

- [ ] **WP98 — The three composite pages: Skills, Magic, Equipment.**
  Goal: give the three nav items that own more than one of today's sections (Finding 4) a real
  intra-page structure, rather than stacking their fragments in a column and calling it a page.
  Deliverables: a Skills page over `_skill_allocation` + `_knowledge_skills`; a Magic page over
  `_talent_selection` + `_spell_selection` + `_power_selection` + `_spirit_selection` +
  `_foci_selection`; an Equipment page over `_resources` + `_vehicles` + `_lifestyle`. Each gets one
  chosen intra-page pattern (sub-tabs, or retained `<details>` groups) applied consistently across
  all three — not three different answers.
  Notes and traps: **decide the intra-page pattern before writing any of the three**, and record the
  call in `spec/decisions-log.md`; this is the only part of the phase where the sketch gives no
  guidance, and picking per-page would leave the app feeling like three different apps. Magic is the
  hard one at five fragments, and it is also the one with real conditional visibility — the whole
  page is gated on the Talent archetype (a Mundane character has no spells, powers, spirits, or
  foci), so its empty state needs designing, not defaulting. Equipment's three fragments all spend
  the *same* nuyen pool, which argues for one shared budget line at page level rather than three
  (and dovetails with WP99). Each fragment keeps its own `hx-target`/id and its own route, exactly
  as now; this WP composes, it does not merge.
  Depends on: WP97.
  Acceptance: `pytest`/`ruff`/`mypy` green; every existing per-step web test still passes with its
  assertions unchanged (the fragments themselves are untouched); an integration test walking
  priorities → skills → magic → equipment through the nav and asserting each page renders all of its
  constituent fragments.

- [ ] **WP99 — The remaining-resources panel.**
  Goal: the sidebar's lower box — one always-visible display of remaining Karma, nuyen, and the
  priority-derived point pools, refreshed on every change from any page.
  Deliverables: a single `_resource_panel_context(character)` builder and `_resource_panel.html`
  partial, rendered into the shell's sidebar and re-sent as an htmx out-of-band swap from every
  step's `POST` so it stays current without the page re-rendering it.
  Notes and traps: most of this already exists and is merely scattered. `Character.karma_remaining`
  / `karma_spent` (`engine/character.py`) is already Phase O's unified ledger — the panel reads it,
  it does not recompute it. Nuyen has `available_nuyen` (`engine/resources.py`) plus the Karma-to-
  nuyen conversion (WP89). What *is* new is that the step templates today print **ten separate
  "remaining" lines** — `attribute_karma_remaining`, `skill_karma_remaining`,
  `knowledge_karma_remaining`, `spell_karma_remaining`, `spirit_karma_remaining`,
  `foci_karma_remaining` / `foci_nuyen_remaining`, `nuyen_remaining` (cyberware),
  `vehicles_nuyen_remaining`, and `_resources`' own — each computed independently in its own context
  builder, each scoped to that step's slice of the budget. Decide deliberately whether the panel
  *replaces* those per-step lines or sits above them: the per-step numbers answer "how much of this
  budget is left for *this* step", which the global ledger genuinely does not, so replacing them
  wholesale would lose information. Recommended: panel shows the global ledger, per-step lines stay.
  Do **not** introduce a second karma-accounting path — if the panel's total ever disagrees with
  `Character.karma_remaining`, the panel is wrong by construction.
  Depends on: WP97 (the shell to mount it in); reads better after WP98 (Equipment's shared nuyen
  pool).
  Acceptance: `pytest`/`ruff`/`mypy` green; a test asserting the panel's Karma figure equals
  `Character.karma_remaining` after a spend on each of ≥3 different pages; a test asserting the
  out-of-band swap is present in a step `POST`'s response body.

- [ ] **WP100 — Theme tokens and a theme selector.**
  Goal: make the graphical furniture — separators, backgrounds, fonts, border weights, the nav's own
  chrome — swappable without touching a single template.
  Deliverables: `app.css`'s token set widened from its current ~14 custom properties to the full
  surface the shell uses; per-theme stylesheets under `static/themes/<name>.css` that redefine
  *only* tokens; a theme preference on `ChargenSession` and a picker in the title bar, selecting
  which theme stylesheet the shell links. Ships with at least two themes so the mechanism is
  actually exercised — the current look, and one that reproduces the sketch's own heavy-rule,
  monospace character.
  Notes and traps: **the constraint that makes this cheap has to be honoured by WP97/WP98, not by
  this WP.** Today's `app.css` selects on ids and tag structure (`#chargen-body > div`,
  `#chargen-body > div > details > summary`) — a theme cannot restyle that without either knowing
  the exact DOM shape or fighting specificity. WP97 and WP98 must emit **semantic class hooks**
  (`.step-nav__item`, `.panel`, `.budget-line`, …) as they rewrite the markup, at which point this
  WP is a token widening plus a `<link>` swap. Done in the other order it means re-editing every
  template a second time. The sketch's chevron connectors between nav items are one theme's idea of
  furniture, not the app's: draw them with `clip-path`/pseudo-elements driven by tokens, so a
  different theme can draw something else or nothing. Keep WP84's two live constraints: nothing may
  set `display` on a `tr` (WP61/WP67's filters toggle the `hidden` attribute), and light/dark both
  stay handled via `prefers-color-scheme` + `color-scheme` — a theme redefines tokens for *both*
  schemes, it does not replace the scheme mechanism.
  Depends on: WP97 and WP98 for the class hooks (see Notes — this is a hard ordering, not a
  preference).
  Acceptance: `pytest`/`ruff`/`mypy` green; a test asserting each shipped theme's stylesheet
  contains **only** custom-property declarations (no selectors beyond `:root` and the scheme
  media queries) — the mechanical proof that themes can't drift into structural CSS; a test
  asserting the selected theme's stylesheet is the one linked in the rendered shell.

- [ ] **WP101 — The i18n key layer.**
  Goal: a string-lookup mechanism plus a locale on the session — the machinery only. No existing
  string is converted here (that is WP102), and only English ships.
  Deliverables: a catalog loader, a `_()` global registered on the Jinja environment, `locale` on
  `ChargenSession`, a language picker in the title bar, and a documented rule for what a key looks
  like. Also: correct `Project Overview.md` — see Notes.
  Notes and traps: **two decisions to make here, and the first is the only genuinely open call in
  this phase.** (1) *Mechanism.* The conventional answer is Babel/gettext, and Jinja2 3.1.6 ships
  `jinja2.ext.i18n` for it — but it adds a dev dependency plus a `.pot`/`.po`/`.mo` extract-and-
  compile workflow, and it does nothing for WP103's problem. The recommended alternative is a
  dict-backed `_()` fed by a loader over `legacy/Chummer/lang/*.xml`, which follows this project's
  existing "parse legacy XML once at startup into indexed frozen dataclasses" pattern
  (`chummer5.data.*`), needs zero new dependencies, and solves WP102 and WP103 with one mechanism.
  The trade is translator-tooling compatibility. **Decide and record it in
  `spec/decisions-log.md` before writing code.** (2) *Key vocabulary.* `legacy/Chummer/lang/en-us
  .xml` already carries **2,767** `<string>` entries with established keys (`String_Karma`,
  `Message_Save_Error_Warning`, …) and four sibling translations (de-de, fr-fr, ja-jp, pt-br,
  zh-cn); reusing those keys where they fit means inheriting real translations for free, and is
  worth a pass before inventing a parallel vocabulary. The injection point is clean:
  `catalogs.py`'s `templates = Jinja2Templates(...)` currently registers **no** filters or globals
  at all, so this is one insertion, not a hunt. Finally, this WP owes a documentation correction:
  `Project Overview.md` lists "all user-facing strings routed through an i18n key layer from day
  one" as in-MVP scope (and leans on i18n as a reason the web UI beats the legacy WinForms one),
  which has never been true. Either fix the claim or date it as deferred-to-here — do not leave it
  overstating what exists.
  Depends on: nothing new. Cheapest to land *before* WP97, so WP97/98's template rewrites can wrap
  their strings as they go rather than being revisited by WP102.
  Acceptance: `pytest`/`ruff`/`mypy` green; a test rendering a page under a non-English locale with
  a two-entry stub catalog and asserting the substitution happens; a test asserting an unknown key
  degrades to something visible and diagnosable rather than rendering blank.

- [ ] **WP102 — Route every chrome string through the key layer.**
  Goal: the mechanical conversion pass — roughly **470** translatable text runs across the page and
  step templates, plus roughly **65** error/warning/diagnostic strings constructed in the
  `web/routes/*` modules.
  Notes and traps: dull but unskippable, and it is the WP most likely to be quietly half-done. The
  strings that hide are the ones not in a template: validation diagnostics built in route modules,
  `<option>` labels assembled in context builders, and anything interpolated
  (`f"..."`) — an interpolated message needs a **parameterised** key, not a concatenation of two
  keys, or it will not survive a language whose word order differs. Number and currency formatting
  is in scope to *identify* but not necessarily to solve: nuyen amounts and the `2,000¥` literal in
  `_resources.html` are locale-sensitive, and this WP should at minimum route them through one
  formatting helper rather than leaving `{:,}`-style formatting scattered. Game-data terms (skill
  names, quality names, metatype names) are **not** in this WP — see WP103.
  Depends on: WP101. Strongly prefer folding into WP97/WP98's own template edits if those land
  after WP101; run as a standalone pass only if they didn't.
  Acceptance: `pytest`/`ruff`/`mypy` green; a repo-wide check (test or lint rule) that the
  templates contain no bare user-facing text outside a `_()` call, so the property is *enforced*
  rather than asserted once and eroded by the next WP.

- [ ] **WP103 — Game-data term translation in the loaders.**
  Goal: the half of i18n that no general-purpose library solves — skill names, quality names,
  metatype names, gear names, categories, all of which come from `legacy/Chummer/data/*.xml` and
  vastly outnumber the chrome strings.
  Deliverables: a lookup layer over `legacy/Chummer/lang/<locale>_data.xml` (which carries
  per-data-file `translate=` attributes keyed by the English name, for each of the five translated
  locales), applied at *display* time in the web layer.
  Notes and traps: **translate for display only — never for identity.** Every catalog in this
  project is keyed by id (or, for `StarterGearItem`, by name — see WP92's note on why that one is
  the exception), selections are stored by id, and the save format records ids; a translated name
  must never reach any of those paths or saves become locale-dependent. That makes the exception
  the trap: name-keyed gear needs its display name and its key kept visibly distinct. Expect
  incomplete coverage — the legacy `_data.xml` files translate what the legacy app shipped, which
  will not be every entry this project offers; the missing-translation fallback is the English
  name, and should be silent rather than an error.
  Depends on: WP101 (the locale on the session; the loader pattern).
  Acceptance: `pytest`/`ruff`/`mypy` green; a test asserting a selection made under a non-English
  locale round-trips through save → load with **English-keyed ids unchanged**; a test asserting an
  untranslated entry falls back to its English name without raising.
