# WP9 — Contacts & starting resources

Status: complete
Ref: [Implementation Plan.md](../Implementation%20Plan.md) — Phase D, WP9.

## Goal

Nuyen, contacts, and a minimal starting-gear stub: `src/chummer5/engine/resources.py` —
Resources-priority-letter → starting nuyen; contacts (connection/loyalty, karma cost beyond free
points); a deliberately minimal starter-gear purchase (flat nuyen deduction against a small
curated list — explicitly not the full gear catalog).

## Log

### 2026-07-17 — WP4 already deferred `<contacts>` parsing here; extended the parser first

`chummer5.io.legacy_chum5`'s module docstring and `load_chum5`'s own docstring both said, verbatim,
"contacts ... picked up by WP9" — so before writing any engine code, extended
`src/chummer5/io/legacy_chum5.py` with a `LegacyContact` dataclass (`name`, `connection`,
`loyalty`, `free`) and a `contacts` field on `LegacyCharacter`, following WP4's established "raw
fields only, no rules interpretation" contract (mirrors `LegacySkillGroup`'s minimalism). Checked
all 11 curated mundane fixtures' `<contacts>` elements directly first: every `<contact>` in every
fixture has `<type>Contact</type>` and `<group>False</group>` — no Enemy or Group-type contacts
anywhere in the curated corpus — so the parser doesn't need (and doesn't add) a filter for either;
flagged in a code comment so a future WP extending the fixture set knows this was checked, not
assumed.

Also picked up the character-level `<contactpoints>` tag (the save format's cached copy of
`Character.ContactPoints`, the CHA*3 free-contact-point budget) as `LegacyCharacter
.contact_points_budget` — not named in WP4's original field list, but essential ground truth for
this WP's free-budget formula (see below), and a raw scalar field fits the same "extract literally
what the file says" contract as everything else `LegacyCharacter` already holds.

### 2026-07-17 — Confirmed `<contactpoints>` is a genuinely reliable cross-check (and found a
red herring along the way)

Before trusting `<contactpoints>` as ground truth, checked where it's actually written in the C#:
`Character.cs`'s `SaveCoreAsync` (the real save routine, ~line 4536) writes `<contactpoints>` from
the `ContactPoints` property (`CharacterSettings.ContactPointsExpression`, default `"{CHAUnaug} *
3"`). Cross-checked this against every one of the 11 curated mundane fixtures by computing each
one's own `CHA` `<totalvalue>` times 3 directly from the raw XML: **all 11 match exactly**
(BLUE/Yeti: 5×3=15, Barrett/Bastion: 4×3=12, Blindfire: 6×3=18, Fuzzy/Gentle Earthquake/Monomax/
SCSi: 2×3=6, Rez0luti0n2.0/Serpent: 3×3=9). This is the same kind of independent cross-loader
validation WP4 ran for `starting_nuyen` against `priorities.xml` — a formula confirmed by two
unrelated sources (the rulebook text and the save data) agreeing, not just one.

The near-miss: there's *also* a `<contactpointsused>` tag in the save files (found via a blind
grep), which sounds like exactly the "points actually spent" figure this WP needs. It is **not** —
checked its value against Yeti (`0`, despite Yeti's own two contacts summing to 15 points) and
traced its origin in the C#: the only write site under that name lives in `PrintToXmlTextWriterCore`
(the character-sheet/export XML generator), not `SaveCoreAsync` (the actual save routine). The
value that shows up in the `.chum5` files is stale/vestigial, not something `SaveCoreAsync` ever
populates correctly for this tag name — a real "don't trust a tag name at face value, trace its
write site" trap. Not used anywhere in this WP's code or tests; documented here so a future agent
grepping the save format doesn't fall into the same trap and try to wire it up as ground truth.

### 2026-07-17 — Rulebook cross-reference: free contact Karma, per-point cost, and a rule the
project's own golden fixture breaks

`pdftotext -layout` on the core rulebook, "Making Connections" (p. 98, character creation step 7)
and its "Additional Purchases & Restrictions" table on the same page: free Karma for contacts =
`Charisma × 3`; each Contact needs Connection ≥ 1 and Loyalty ≥ 1; each point of Connection or
Loyalty beyond the free budget costs 1 Karma (minimum 2 Karma per contact); and — the part that
turned into this WP's main finding — **"a single contact may not have more than 7 Karma spent on
them at character creation."** Cross-checked this last rule against the legacy engine too:
`CharacterCreate.cs`'s character-validity check (~line 19991) does invalidate a finished character
if any contact exceeds 7 points, unless the Friends in High Places quality is present (checked via
`Connection >= 8`).

Then checked this rule against every mundane fixture's raw `<contact>` connection/loyalty pairs —
and found `Yeti-#ffffff2.chum5`, this project's own priority-build golden fixture (load-bearing for
WP6/WP7's allocation tests), has a contact at Connection 5/Loyalty 4 (9 points) with no Friends in
High Places quality anywhere in its quality list (checked: Technomancer, Infirm, Impassive,
Paranoia, Faceless, Data Anomaly — none of them). This is a real rulebook rule the accepted ground
truth violates outright — not a parsing bug, not a misread page number. Given the choice between
"enforce the rule and make the engine unable to reproduce its own reference fixture" and "model the
rule as data (a computable `karma_cost`) without gating construction on it," went with the latter —
the same kind of judgment call WP8 made when it found the negative-quality karma cap had zero
real-content coverage, except mirrored: here real content actively *contradicts* a documented rule
rather than merely failing to exercise it. Recorded both the rulebook text and this contradiction in
`spec/rulebooks/learnings.md`'s new WP9 entry, and in `chummer5.engine.resources`'s module
docstring, so neither gets silently rediscovered or assumed to be a bug in this project's own code.

Symmetrically: **the free-budget check is also not a hard cap.** Checked the corpus for
over-budget spends before assuming characters always stay under budget: `BLUE.chum5` (21 spent vs.
15 budget), `Rez0luti0n2.0.chum5` (10 vs. 9), and `Serpent.chum5` (13 vs. 9) all exceed their free
contact-point budget and pay the difference in Karma per `CharacterCreate.cs`'s
`intKarmaPointsRemain -= Math.Max(0, intPointsInContacts - intContactPoints) + ...` (~line 13002).
So `create_contact_selection` computes `karma_cost` unconditionally rather than raising once spend
exceeds the free budget — consistent with the Implementation Plan's own phrasing ("karma cost
*beyond* free points", not "reject spend beyond free points").

### 2026-07-17 — Starter gear: a hand-curated, flat-cost list, not a data loader

The Implementation Plan is explicit that this is "a deliberately minimal starter-gear purchase
(flat nuyen deduction against a small curated list — explicitly not the full gear catalog)" — so,
unlike every other `chummer5.data` module, this isn't a new XML loader. Picked 5 real, SR5-sourced,
flat-cost (no `Rating`-scaled formula like Fake SIN's `Rating * 2500`) items by reading
`legacy/Chummer/data/{gear,armor,weapons}.xml` directly and hand-copying their names/costs: Meta
Link (100¥, a commlink), Certified Credstick, Standard (5¥), Armor Jacket (1000¥), Ares Predator V
(725¥), Combat Knife (300¥). These are real numbers from the actual data files, not invented, even
though the catalog itself is hand-typed rather than loaded — cross-checking against genuine SR5
prices was worth the extra minute over making numbers up, and costs nothing extra to maintain since
the list is this short.

Deliberately did not attempt to reproduce any fixture's actual `<nuyen>` (remaining) value against
this stub — Yeti's own remaining nuyen (1145 of 6000 starting) reflects the full legacy gear
catalog's actual purchases (a `Living Persona`, `AR Gloves`, and much more, per its `<gears>` list),
which this deliberately minimal 5-item stand-in was never going to reconstruct. `starting_nuyen()`
itself *is* cross-checked against every fixture's `<startingnuyen>` (already validated once in WP4;
re-validated here through the new `chummer5.engine.resources.starting_nuyen` function specifically,
not just WP2's raw loader) — that's the one number in this area both real and fully reproducible.

### Design decisions

- **`Contact` has no catalog to validate against, unlike every other selection module built so
  far** (metatypes, qualities, skills all cross-reference a `chummer5.data` catalog). A contact's
  name/connection/loyalty are the player's own invention — there's nothing in `legacy/Chummer/data`
  to check an id against. `create_contact_selection` therefore validates only the two things that
  *are* real rules (Connection/Loyalty ≥ 1), not id membership.
- **`create_contact_selection` takes a `Character`, not a bare `charisma: int`.** Every other
  `create_*_selection` function in this codebase takes static priority-table data, not a
  `Character` — but the contact-point budget genuinely depends on the *finalized* CHA value
  (metatype minimum + points spent + improvements), the same reason `chummer5.engine.skills`'s
  `dice_pool`/`skill_rating` (not `create_skill_allocation`) take a `Character`. Mirrors that
  precedent rather than forcing every caller to compute `character.attribute_value("CHA")`
  themselves first.
- **Two rules from the rulebook are deliberately not enforced as `ValueError`s**: the per-contact
  7-point cap (contradicted by Yeti) and the free-budget cap itself (contradicted by
  BLUE/Rez0luti0n2.0/Serpent). Both are documented as computed data (`Contact.points`,
  `ContactSelection.karma_cost`) rather than silently dropped or silently enforced against evidence
  that they aren't hard gates in practice. See the Log entries above and the module docstring.
- **`STARTER_GEAR_CATALOG` lives as a hardcoded tuple in `chummer5.engine.resources`, not a new
  `chummer5.data` loader.** Follows the Implementation Plan's explicit instruction rather than
  over-building a gear-catalog parser this WP doesn't need and a later WP would have to redesign
  around cyberware/vehicles/full gear anyway (out of MVP scope per the Project Overview).
- **`create_resources_selection` allows repeated gear names** (buying two Credsticks), unlike
  `create_quality_selection`'s duplicate-id rejection — a quality can only be taken once per its
  `<limit>` semantics (see WP8), but nothing about gear purchases works that way; rejecting repeats
  would be inventing a restriction with no rules basis.
- **No `Character` field added for `ContactSelection`/`ResourcesSelection`,** mirroring WP7/WP8's
  identical choice for `SkillAllocation`/`QualitySelection` — WP10 is still where the Implementation
  Plan schedules wiring every engine module's selection into one finished-character build.

### Implementation

- `src/chummer5/io/legacy_chum5.py` (extended): `LegacyContact` (`name`, `connection`, `loyalty`,
  `free`); `LegacyCharacter.contacts` and `.contact_points_budget` (from `<contactpoints>`);
  `_parse_contact`/`_parse_contacts` helpers; docstrings updated to drop the "contacts picked up by
  WP9" forward-reference now that it's done.
- `src/chummer5/engine/resources.py` (new): `FREE_CONTACT_POINTS_PER_CHARISMA` (3),
  `KARMA_PER_EXCESS_CONTACT_POINT` (1), `MIN_CONTACT_RATING` (1); `Contact` (+`.points` property);
  `ContactSelection` + `create_contact_selection()`; `StarterGearItem`, `STARTER_GEAR_CATALOG` (5
  hand-curated flat-cost items); `ResourcesSelection` + `starting_nuyen()` +
  `create_resources_selection()`.
- `spec/rulebooks/learnings.md` (extended, untracked — see WP8's precedent for why
  `spec/rulebooks/` stays gitignored): new WP9 entry with the "Making Connections" rulebook extract
  and the Yeti 7-point-cap contradiction.

### Verification

- `uv run python -m pytest -q`: 159 passed (125 pre-existing from WP1-WP8 + 34 new: 17 in
  `tests/unit/test_resources.py`, 14 in `tests/integration/test_legacy_chum5.py` (parametrized
  `contact_points_budget` check across all 11 fixtures, Yeti's own two contacts, Monomax's one free
  contact), 3 in `tests/integration/test_character_fixtures.py` (cross-corpus CHA*3 budget check,
  Yeti's full contact-selection build end to end, `starting_nuyen()` re-validated via the engine
  function across all 11 fixtures)). Unit coverage: `Contact.points` (sum, floor-at-2, free=0);
  budget/karma-cost math within and beyond the free budget; free contacts excluded from spend;
  Connection/Loyalty-below-1 rejection; an explicit test asserting a >7-point contact is *not*
  rejected (documents the deliberate non-enforcement); empty selection; `starting_nuyen` hand-checked
  against the Standard Resources table; gear selection within budget, empty, repeated items,
  unknown-item rejection, budget-overspend rejection.
- `uv run python -m ruff check .` / `ruff format --check .`: clean (ran `ruff format` once to fix
  two files' line-wrapping before the final check).
- `uv run python -m mypy src`: clean, strict mode.
- Environment note (repeat of WP2-WP8's, not a new finding): checkout mounted at
  `/workspaces/chummer5_py`, `.devcontainer/devcontainer.json` pins `workspaceFolder` to
  `/workspace`; used `uv run python -m {pytest,ruff,mypy}` throughout, per the documented
  workaround.
- Rulebook PDF **was** consulted this WP (`pdftotext -layout`, "Making Connections" + "Additional
  Purchases & Restrictions", p. 98) — needed both the free-Karma formula's source-of-truth
  confirmation (the legacy code default alone doesn't prove it's the *core rulebook's* number
  rather than a house-rule-adjustable setting, same reasoning WP8 applied to the quality karma
  cap) and the per-contact Karma cap's exact wording, which is what led to finding the Yeti
  contradiction. Learnings recorded in `spec/rulebooks/learnings.md`'s new WP9 section.

## Files touched

- `src/chummer5/io/legacy_chum5.py` (extended: `LegacyContact`, `contacts`/`contact_points_budget`
  fields, parsing helpers, docstring updates)
- `src/chummer5/engine/resources.py` (new)
- `tests/unit/test_resources.py` (new)
- `tests/integration/test_legacy_chum5.py` (extended: contact-points-budget registry, Yeti/Monomax
  contact tests)
- `tests/integration/test_character_fixtures.py` (extended: cross-corpus budget check, Yeti
  contacts end-to-end, engine-level starting-nuyen re-check)
- `spec/rulebooks/learnings.md` (extended, **untracked** — see WP8's note on why
  `spec/rulebooks/` stays gitignored; this file quotes rulebook text directly)
- `spec/worklogs/WP9.md` (new, this file)
- `spec/Implementation Plan.md` (WP9 checkbox ticked)

## Outcome

WP9 complete: `chummer5.engine.resources` adds contacts (`Contact`, `create_contact_selection` —
free budget `CHA × 3`, `karma_cost` for spend beyond it, both confirmed against the core rulebook
and cross-validated against all 11 mundane fixtures' `<contactpoints>` tag) and starting resources
(`starting_nuyen`, a 5-item hand-curated `STARTER_GEAR_CATALOG`, `create_resources_selection`).
`chummer5.io.legacy_chum5` gained the `<contacts>`/`<contactpoints>` parsing WP4 explicitly deferred
here. The notable rules finding: the core rulebook's "no contact may have more than 7 Karma spent on
it at creation" cap is real, but this project's own `Yeti-#ffffff2.chum5` golden fixture violates
it with no Friends in High Places quality present — so MVP models the number without gating
construction on it, documented in both `spec/rulebooks/learnings.md` and the module docstring
rather than silently enforced or silently dropped.
