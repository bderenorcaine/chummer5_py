# WP8 — Quality selection & minimal Improvement bonuses

Status: complete
Ref: [Implementation Plan.md](../Implementation%20Plan.md) — Phase D, WP8.

## Goal

Qualities affect karma and, for the supported subset, feed the Improvement engine: positive/negative
quality picking, karma cost, the negative-quality karma cap; only WP3's "MVP-supported"
(`BonusSupport.FLAT_BONUS`) qualities produce `Improvement` records.

## Log

### 2026-07-17 — The MVP-offered quality catalog collapses to 3, all Positive

Re-read WP3's `chummer5.data.qualities` docstring before writing anything: it already states the
design WP8 has to follow — "WP8 offers only `FLAT_BONUS` qualities to the player; `NOT_YET_SUPPORTED`
ones are excluded from the offered list rather than silently applied with their bonus dropped." The
Implementation Plan's own WP8 acceptance criterion ("an explicit test that an unsupported-bonus
quality is excluded from the offered list rather than silently mis-applied") confirms this reading —
the *offered* catalog itself is `FLAT_BONUS`-only, not "any SR5 quality, but only some produce an
Improvement." Cross-checked against WP3's own count (`spec/worklogs/WP3.md`): only 3 of the 96 SR5
qualities are `FLAT_BONUS` — Catlike, Double-Jointed, Natural Athlete — and all three happen to be
Positive-category (confirmed directly from `qualities.xml`: all three carry `<category>Positive`).
**This means MVP's quality picker cannot currently offer a single Negative quality** — every
Negative-category SR5 quality's `<bonus>` shape (or lack of one) falls outside the flat-bonus
classifier. This is a real, load-bearing consequence of WP3's classifier, not a WP8 oversight, so
it's flagged here rather than left implicit.

Practical effect: the "negative-quality karma cap" the Implementation Plan explicitly asks for as a
deliverable is real, general rules logic (implemented, tested, and correct) that **no currently
reachable player selection can actually trigger** — cross-checked the full mundane fixture corpus
(all 11 `.chum5` files) for any FLAT_BONUS quality and found only one hit at all (`Blindfire.chum5`'s
Catlike — see below), itself Positive. The cap is therefore proven with synthetic `Quality` instances
(hand-authored, same shape as WP3's synthetic flat-attribute-bonus fixture), the same "prove the rule
in isolation before real content exercises it" pattern WP5 established for Improvement dedup and WP7
used for the dice-pool formula.

### 2026-07-17 — Rulebook cross-reference: the 25/25 karma split, and confirming it's two independent caps

The Implementation Plan names "negative-quality karma cap" but doesn't state the number or whether
it's paired with a symmetric positive-side cap — checked the PDF directly rather than assuming.
`pdftotext -layout` on `spec/rulebooks/Shadowrun_Fifth_Edition_Core_Rulebook.pdf`, "Choose Qualities"
step of character creation: "at creation characters can only possess at most 25 Karma worth of
Positive Qualities and 25 Karma worth of Negative Qualities" — two independent 25-karma caps, one per
side, not a single shared budget. Cross-checked this against the legacy C# to confirm it's enforced
as a hard rule, not a soft suggestion: `CharacterSettings.cs`'s `_intQualityKarmaLimit = 25` (field
default) and `_blnExceedPositiveQualities`/`_blnExceedNegativeQualities` both defaulting to `false`
(C# bool default, no override in this checkout) — `CharacterCreate.cs`'s character-validity check
(~line 19961) compares `PositiveQualityLimitKarma`/`NegativeQualityLimitKarma` against the 25-karma
limit independently and rejects finishing character creation if either is exceeded, unless the
(off-by-default) override settings are on. Recorded the extracted rulebook text and this
cross-reference in `spec/rulebooks/learnings.md` (new file — first rulebook-PDF consultation to
produce a learnings note; no prior WP had created one, per WP6/WP7's "rulebook not consulted this
WP" notes) per the task instructions, so a future WP doesn't have to re-extract the same passage.
**Noticed after writing it: `spec/rulebooks/` is entirely gitignored** (`.gitignore`: "Copyrighted
reference material kept locally for rules lookups, not for redistribution"). Since the file directly
quotes rulebook text, left it untracked rather than force-adding it against that stated policy — it
still persists on disk in this checkout for a future agent to read directly, just not via `git
log`/GitHub. Flagging this here so a future WP doesn't assume "no `spec/rulebooks/*.md` file" means
"no prior WP ever wrote one."

### 2026-07-17 — `Blindfire.chum5`: the one real-corpus fixture touching an MVP-offered quality

Scanned all 11 mundane fixtures' `<qualities>` lists for any of the 3 FLAT_BONUS names. Only
`Blindfire.chum5` hits — it has Catlike (`karma=7`, `source=SR5`), alongside seven other qualities
sourced from later books (CF/RF/CA/RG) that are out of MVP scope entirely and one more SR5 quality
(`Combat Paralysis`, Negative) that's `NOT_YET_SUPPORTED`. This rules out treating Blindfire as a
"build the whole character's quality list through the engine" fixture the way Yeti serves WP6/WP7 —
most of its qualities aren't constructible under MVP's scope rules at all. Used it narrowly instead:
`test_blindfire_catlike_quality_matches_engine_end_to_end` cross-references only the Catlike entry
(id/karma match the catalog, `create_quality_selection` reproduces its karma cost, and
`apply_quality_improvements` produces the expected `+2 Sneaking` Improvement) — the same "extract
what real ground truth actually supports, no more" discipline WP6 applied to the metavariant
fixtures and WP7 applied to the "no stored dice pool" gap.

### Design decisions

- **`mvp_quality_catalog()` is a pure filter function, not folded into `create_quality_selection`.**
  Mirrors WP6's `sr5_metatypes()`/`metatype_choices()` split (a catalog-narrowing step callable
  independently of the thing that validates a specific selection against it) — a future UI quality
  picker needs "what can I show the player" (`mvp_quality_catalog`) as a distinct operation from "is
  this specific selection valid" (`create_quality_selection`).
- **`QualitySelection.positive_karma`/`negative_karma` are both non-negative magnitudes, `karma_cost`
  is the signed net delta.** Chose this split over exposing only a signed `karma_cost` because the
  25-karma cap check needs the two magnitudes independently (see the caps-are-independent test) —
  collapsing to one signed total before checking would let a large positive spend and a large
  negative refund silently net out to "under 25" while either side individually broke the rule.
- **No `Character` field for `QualitySelection`,** mirroring WP7's identical choice for
  `SkillAllocation`: `apply_quality_improvements` reads a `Character` (for `.improvements`) but the
  selection itself isn't stored on it. WP10 is where the Implementation Plan already schedules wiring
  every engine module into one finished-character build.
- **`apply_quality_improvements` mutates `character.improvements` in place rather than returning a
  tuple of `Improvement`s for the caller to add.** `Character.improvements` is already a live,
  mutable `ImprovementIndex` (WP6 built it this way specifically "so WP8's quality bonuses have a
  place to land without reshaping `Character` later") — returning improvements instead would force
  every caller to immediately turn around and call `.add()` in a loop, adding a step with no
  information content. `source_id=quality.id` (not a synthesized composite) keeps
  `ImprovementIndex.remove_source(ImprovementSource.QUALITY, quality.id)` directly usable to retract
  one quality's effects later (e.g. a UI "remove this quality" action), which is exactly the
  operation WP5 designed `remove_source` around.
- **Duplicate-selection rejection uses `set`/`list.count`, not `Counter`, and treats every quality as
  non-repeatable.** None of the 3 currently-offered qualities have a `<limit>` allowing multiple
  purchases (checked: none of Catlike/Double-Jointed/Natural Athlete carry a `<limit>` element at
  all) — a repeatable-quality allowance would be speculative scaffolding for a case nothing in
  MVP's scope exercises, so `create_quality_selection` just rejects any id appearing twice, the
  simplest rule consistent with the current catalog. If a future book's data introduces a repeatable
  `FLAT_BONUS` quality, this is the one place that would need to change.

### Implementation

- `src/chummer5/engine/qualities.py` (new): `QUALITY_KARMA_LIMIT` (25); `mvp_quality_catalog()`
  (filters to `BonusSupport.FLAT_BONUS`); `QualitySelection` + `create_quality_selection()`
  (unknown-id/duplicate/25-karma-cap validation, mirroring WP6/WP7's construction-time-`ValueError`
  style); `apply_quality_improvements()` (adds each selected quality's `FlatBonus`es to
  `character.improvements` as `Improvement`s with `source_type=ImprovementSource.QUALITY`).
- `spec/rulebooks/learnings.md` (new): the 25/25 karma-limit rulebook extract, cross-referenced
  against the legacy enforcement site.

### Verification

- `uv run python -m pytest -q`: 125 passed (109 pre-existing from WP1-WP7 + 15 new in
  `tests/unit/test_quality_selection.py` + 1 new in `tests/integration/test_character_fixtures.py`).
  Unit coverage: `mvp_quality_catalog` returns exactly the 3 FLAT_BONUS qualities (all Positive) and
  excludes a NOT_YET_SUPPORTED one (Analytical Mind) from both the catalog and a selection attempt;
  single/multiple/empty positive selections and their summed karma; unknown-id and duplicate-id
  rejection; positive-karma-over-limit and negative-karma-over-limit rejection (via synthetic
  qualities, per the reasoning above); the two 25-karma caps checked independently (a selection
  under both individual limits but over their naive sum); `apply_quality_improvements` for a
  single-target quality (Catlike -> Sneaking), a multi-target quality from one source (Natural
  Athlete -> Running + Gymnastics), an attribute-target synthetic quality, and retraction via
  `ImprovementIndex.remove_source`. Fixture coverage:
  `test_blindfire_catlike_quality_matches_engine_end_to_end` cross-references `Blindfire.chum5`'s
  Catlike entry (id/karma) against the catalog and validates the full
  `create_quality_selection` -> `apply_quality_improvements` -> `character.improvements.resolve()`
  path against it.
- `uv run python -m ruff check .` / `ruff format --check .`: clean (several docstring/comment
  line-length wraps needed during development, fixed before the final run).
- `uv run python -m mypy src`: clean, strict mode.
- Environment note (repeat of WP2-WP7's, not a new finding): checkout mounted at
  `/workspaces/chummer5_py`, `.devcontainer/devcontainer.json` pins `workspaceFolder` to
  `/workspace`; used `uv run python -m {pytest,ruff,mypy}` throughout, per the documented
  workaround.
- Rulebook PDF **was** consulted this WP (`pdftotext -layout`, "Choose Qualities" character-creation
  step) — the Implementation Plan named the negative-quality karma cap as a deliverable but not its
  value or whether it pairs with a positive-side cap, and neither `qualities.xml` nor any WP1-WP7
  data file states the 25/25 split as a value (it lives in `CharacterSettings.cs` as a code default,
  which confirms the *mechanism* but not that it's the *core rulebook's* number rather than a
  house-rule-adjustable default). Learnings recorded in `spec/rulebooks/learnings.md` (new file).

## Files touched

- `src/chummer5/engine/qualities.py` (new)
- `tests/unit/test_quality_selection.py` (new)
- `tests/integration/test_character_fixtures.py` (extended: Blindfire/Catlike fixture test)
- `spec/rulebooks/learnings.md` (new, **untracked** — `spec/rulebooks/` is entirely gitignored,
  "copyrighted reference material kept locally for rules lookups, not for redistribution"; this file
  quotes rulebook text directly, so it stays local rather than overriding that policy. It persists on
  disk in this checkout for a future agent to read even though `git log`/GitHub won't show it — see
  the log entry above for why it wasn't force-added.)
- `spec/worklogs/WP8.md` (new, this file)
- `spec/Implementation Plan.md` (WP8 checkbox ticked)

## Outcome

WP8 complete: `mvp_quality_catalog()` restricts WP3's SR5-scoped quality catalog to the 3
`FLAT_BONUS` qualities (Catlike, Double-Jointed, Natural Athlete — all Positive, a real consequence
of WP3's classifier worth carrying forward rather than rediscovering); `create_quality_selection()`
validates a pick against that catalog plus the core rulebook's 25-karma-per-side Positive/Negative
quality cap (checked independently per side, confirmed against both the rulebook text and the legacy
engine's enforcement); `apply_quality_improvements()` lands each selected quality's flat bonuses onto
`Character.improvements` as `Improvement`s, retractable via WP5's `remove_source`. Validated against
`Blindfire.chum5`'s Catlike entry (the only real-corpus fixture touching an MVP-offered quality) and,
for the karma-cap rule itself — which no real selection can currently trigger, since every offered
quality is Positive — via synthetic `Quality` fixtures, the same pattern WP5/WP7 used for rules that
real data doesn't yet exercise.
