[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase S — Post-MVP: Test fixture expansion (research-intro; WP60 onward pending its own strategy pass)

**Why now.** Raised in the same 2026-07-24 session as Phase Q. The project's regression oracle has
been the same fixed 34-file `legacy/Chummer.Tests/TestFiles/` corpus since WP4, and it is thin in a
way that's been re-flagged by nearly every phase since: only **3 of 34** fixtures are
`buildmethod = Priority` at all — `Yeti-#ffffff2.chum5` (mundane), `Miko.chum5` (Elf Magician),
`Wesson.chum5` (Human Adept) — and each backs exactly one phase's own content in isolation. No
fixture is simultaneously magic-enabled *and* cyberware-bearing (Phase J's WP35 note), none exercises
the Cyber Implant Weapon → Weapon Accessory two-level nesting case Phase K's own intro flags as
undecided, and Phase M/N/O's worklogs repeatedly fall back to "hand-verified, no fixture" for content
the corpus simply never happens to contain. The corpus can't grow on its own — it's a fixed snapshot
of real characters, not a generator — so more coverage has to come from somewhere else.

**Checked this session, load-bearing for how this phase should be scoped: no .NET toolchain is
available in this devcontainer.** `which dotnet mono` returns nothing, and
`legacy/Chummer.Tests/Chummer.Tests.csproj` is an old-style `packages.config` project (pre-SDK-style),
making a from-scratch build meaningfully harder than a modern `dotnet build` even if a runtime were
installed. **This means "drive the actual legacy engine to generate new golden `.chum5` fixtures for
hand-designed synthetic characters" — the highest-fidelity option, since it would produce real
legacy-computed truth instead of hand-computed truth — is very likely not viable here**, though this
needs confirming (not just inferring from a missing binary) before being ruled out, since a
prior-session environment might differ. If it's genuinely not viable, the realistic path is
hand-authored synthetic fixtures cross-checked directly against the rulebook (the same rigor this
project already applies to "hand-authored cases checked directly against `priorities.xml`" for WP6,
and to every `pdftotext -layout`-sourced formula in `learnings.md`) rather than against legacy output.

- [ ] **WP59 — Fixture-strategy research pass: confirm the legacy-toolchain question, inventory real
  coverage gaps, and decide a fixture-authoring mechanism before writing any new fixtures.**
  Goal: settle *how* new fixtures get created (legacy-engine-generated vs. hand-authored-and-cited)
  and *what* they should cover, before committing engine-content WPs to either path.
  Deliverables:
  - Definitively confirm whether any environment available to this project (this devcontainer, or a
    documented one-off outside it) can build and run `Chummer.Tests` headlessly to produce a new
    `.chum5` for a synthetic character definition. If yes, prototype the smallest possible case (one
    new mundane character) end to end before assuming the path scales. If no, document why concretely
    (missing runtime confirmed, or a real build failure — not just "seems unlikely").
  - Inventory concrete coverage gaps by phase, cross-checking the "hand-verified, no fixture" and
    "no fixture exercises X" call-outs already scattered across `Implementation Plan.md`'s phase files
    and `learnings.md` (e.g. Phase K's two-level cyberware nesting, Phase J's Essence+Magic
    interaction now covered by WP35 but only via hand-derived cases, any Sum-to-Ten build combined
    with magic or cyberware) rather than guessing at what's missing from scratch.
  - Decide and document the fixture format for whichever mechanism wins: a new `.chum5`-shaped file
    (if legacy-generated) slotting into the existing `tests/fixtures/` + `mundane_chum5.py`-style
    registry, or a lighter synthetic-input format (e.g. a small dataclass/JSON literal plus its
    hand-derived expected values and rulebook citations) if hand-authored — mirroring how synthetic
    data already proves engine primitives in isolation (WP5's Improvement resolution tests, WP30's
    Essence tests) before this phase decides whether that pattern extends to whole-character fixtures
    or stays primitive-scoped.
  - Produce the resulting fixture-authoring WP list (numbers, scope, which gaps each closes) as an
    addition to this phase file, the same way Phase K's own intro was scoped before WP36-42 were
    written.
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` untouched and green (research only, no source/fixture changes
  yet); this phase file updated with a concrete WP60+ breakdown, the legacy-toolchain question
  answered definitively (not left open), and each proposed new fixture tied to a specific,
  currently-real gap rather than speculative future-proofing.
