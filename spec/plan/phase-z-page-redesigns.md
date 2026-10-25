[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase Z — Post-MVP: page redesigns (WP143-150, open-ended)

**Why now.** Raised 2026-10-05 with a hand-drawn redesign of the Priorities page
(`examples/ui/priorities.png` / `.svg`, committed alongside this file). Phase W (WP97-106) built the
application shell and moved every step into it *unchanged*. Each step's contents are still the
pre-shell accordion forms. This phase is where individual pages get redesigned for the shell, one
sketch at a time.

**This phase is open-ended.** More page redesigns are likely to follow. **Add each one here** as
its own block of WPs, with its sketch under `examples/ui/` and a dated rulings table like the
Priorities one below. Don't open a new phase per page. Claim WP numbers from the index's "Next
unclaimed WP number" as usual, and update the "WP143-150" range in this file's title and in the
index's phase row. The **standing design rules** below apply to every redesign in this phase, not
just Priorities. Extend them when a later sketch settles something new.

**How to read the sketches.** The user's line conventions:

- **Solid lines** are visible lines in the real UI: panel borders, control outlines.
- **Dashed boxes** only show the size of a region. They have no border in the real UI. The
  "Explanatory Text" and "Confirmation Text" boxes are examples.
- **Dashed or dotted lines between elements** are visual aids for the reader, such as the dot
  leaders in the Sum-to-Ten rows. They may literally be rendered as dashed or dotted lines.

Alignment in the sketches is approximate. Fix it wherever the result looks better (user ruling
2026-10-05).

---

#### Standing design rules (all redesigns)

1. **Messages never sit above controls.** Errors, warnings and notices that come and go must not
   push the controls down. Several existing pages put warnings at the top, so the layout jumps and
   the player's next click misses its target. In a redesigned page, these messages go at the bottom
   or somewhere else where they can't move a control. The same goes for anything that appears or
   disappears next to a control, such as a button that is only sometimes relevant: it reserves its
   space (`visibility: hidden`, not `display: none`).
2. **A centred column of comfortable width, not full-pane stretch.** A redesigned page's content
   (heading included) is one column. It is capped at a comfortable reading width and centred
   horizontally in the content pane, top-aligned (not vertically centred). Below the cap it fills
   the pane with a 1rem margin on each side. **It must look good in portrait mode.** The shell
   already stacks the nav above the content below 40rem (`app.css`). On a phone the page is that
   column at full width.
3. **No collapsible wrapper on a page that is a single panel.** The old `<details>`/`<summary>`
   accordion heading on a step fragment is pointless when the page shows nothing else. A
   redesigned page drops it. The page heading stays a plain heading.
4. **Client behaviour lives in static files**: `static/app.js`, or a vendored library under
   `static/vendor/<name>/` with its `LICENSE` and `VENDORED.md`, plus an entry in the repo's
   `NOTICE`. This is what WP141's CSP requires (`script-src 'self'`, no inline script, no
   `hx-on`, no htmx expressions evaluated with `new Function`).
   `test_no_template_carries_code_the_csp_would_block` and
   `test_every_page_under_every_theme_is_csp_clean` must stay green.
5. **Styling uses the theme tokens only** (`var(--...)`, see the WP100 note at the top of
   `app.css`). New styles go in `app.css`, under a section named for the page. Check every new
   widget under all four themes, in both light and dark.
6. **Every string is an i18n key** (`src/chummer5/lang/README.md`). Reuse legacy keys where the
   English matches exactly.
7. **The devcontainer has no browser and no Node.** pytest covers the server side and the rendered
   markup (attributes, hidden inputs, which script is included). It cannot cover drag, wheel,
   keyboard or dialog behaviour. A WP with client-side behaviour ends with a **manual browser
   checklist** in its worklog, marked "not run here", for the user to work through. Keep
   client-side logic small and stateless so that checklist stays short. Anything that is a rule
   (budgets, validity, conversions) is decided server-side and handed to the script as data.

---

#### Redesign 1 — Priorities (WP143-145)

**Sketch:** `examples/ui/priorities.png`. It shows two layouts for one panel, chosen by a build
method dropdown above it:

- **Priority:** the fixed letters A–E run down the left. Beside each is the category placed at
  that letter (Heritage, Talent, Attributes, Skills, Resources). The player **reorders the
  categories** against the fixed letters. Today it's the other way round: one letter dropdown per
  category.
- **Sum-to-Ten:** one row per category in fixed order. Each row has a dot leader to its value,
  "E (0)" (letter, then point cost), and a "∑ 0 / 10" row closes the list. Letters may repeat here,
  which is why this mode keeps the per-category choice.
- **Both layouts** have explanatory text at the top, then the Metatype dropdown, CONFIRM, and a
  text region at the bottom.

**The user's rulings (2026-10-05):**

| Question | Ruling |
|---|---|
| How are categories reordered in Priority mode? | **Drag-to-reorder**, using **SortableJS** (vendored). Swapping on dropdown change was rejected: working out which swaps reach the order you want is annoying. Dragging a tile *inserts* it, and the tiles in between shift by one. |
| How does a Sum-to-Ten value change? | **Spinner boxes.** The scroll wheel changes the value **only while the spinner has focus**, so scrolling the page over the panel never changes a value by accident. |
| Sum-to-Ten total off target | The ∑ row is **highlighted** and CONFIRM is **disabled**. |
| Sum-to-Ten starting values | **All E (0 / 10)**, deliberately. There must be no impression of a "default" Sum-to-Ten distribution. |
| Switching from Sum-to-Ten to Priority | The new order **minimises the total letter distance** to the previous selection (A→B is 1 step, A→C is 2, and so on). Ties are broken by display order: Heritage, Talent, Attributes, Skills, Resources. |
| Explanatory text | **Changes with the method.** |
| Showing what each priority gives | The bottom text region **always shows what the current form selects**, i.e. what each placed priority gives. CONFIRM changes a status from unconfirmed to confirmed. It no longer reveals a summary. |
| Leaving the page with unconfirmed changes | A **dialog** with three choices: **Confirm** (only when the form is confirmable), **Stay** on the page, or **Revert** to the confirmed priorities. Silently keeping the edits was rejected: the player might believe they're using the new priorities while the rest of the character still uses the old ones. |
| Warnings and errors | **At the bottom**, never above the controls (standing rule 1). |
| Collapsing, width | No collapsible wrapper. A comfortable width, centred, good in portrait (standing rules 2-3). |

**Defaults this file sets (not user rulings; change them here if they turn out wrong):**

- **Switching from Priority to Sum-to-Ten keeps the letters** for a character whose priorities have
  been confirmed. Five distinct letters always total exactly 10. A **never-confirmed** character
  switching to Sum-to-Ten starts at all E instead. Otherwise the session's default priority order
  would show up as exactly the "default distribution" the user ruled out.
- **Summary content:** Heritage gives the chosen metatype and its special attribute points.
  Talent gives the names of the talent options that letter offers. Attributes gives points. Skills
  gives skill points and skill group points. Resources gives nuyen. In the "changed" state, each
  line that differs from the confirmed priorities reads "old → new". Lines that didn't change read
  as usual.
- **Keyboard reordering:** Alt+↑ / Alt+↓ on a focused Priority tile moves it one row. Dragging
  alone would lock keyboard users out.
- **An on-page Revert button** sits beside CONFIRM. It is visible only in the "changed" state, but
  its space is always reserved.
- **No metatype is preselected for a never-confirmed character** (WP143). The Metatype field
  opens on a "Choose metatype" placeholder, so the page opens unconfirmable. This is the same
  "never silently pick a metatype" rule the preview applies.
- **Leaving with "Revert" continues the navigation.** Nothing server-side changed, so reverting
  just drops the form's edits and goes where the player was headed. "Confirm" confirms, then
  continues. "Stay" cancels the navigation.

**Finding 1 — the POST contract can stay exactly as it is.** `POST /ui/priorities` takes
`build_method`, `metatype_id` and five `<category>_letter` fields today. Both new layouts can post
exactly that:

- **Priority mode:** each draggable tile carries a hidden `<category>_letter` input. After every
  reorder, the script rewrites each tile's value to the letter of the row it now sits in.
- **Sum-to-Ten:** each spinner writes its letter into its row's hidden `<category>_letter` input.

So `submit_priorities` itself needs no change. Neither do the WP138 store-on-first-confirm path or
WP19's carry-forward and stale-selection logic. The duplicate-letter check stays as a server-side
guard, even though dragging makes duplicates impossible.

**Finding 2 — "dirty" is decided server-side, not in the script.** The session holds only the
*confirmed* selection (`ChargenSession.heritage_letter` and the rest, `build_method`,
`metatype_id`). Form edits exist only in the browser until CONFIRM. A new read-only endpoint
renders the status and summary for whatever the form currently holds, compared against the session.
Every response carries the status as data the script can read, e.g. `data-priority-status=
"unconfirmed|confirmed|changed"` and `data-priority-confirmable="true|false"`. The leave dialog
(WP145) and the CONFIRM button's state read those attributes. The script never compares
selections itself.

**Finding 3 — there is no browser test harness**, and adding one is not in scope (standing rule
7). That is why WP143 puts everything rule-bearing on the server, and why WP144/145's script is
deliberately thin.

**Suggested models (judgement call, 2026-10-05).** WP143 suits Sonnet. Its contract is fully
specified and testable with pytest. WP144 and WP145 are Opus: nothing can test them here, so the
implementer has to anticipate the browser traps themselves. If either runs on Sonnet anyway, follow
it with an Opus `/code-review high`.

---

- [x] **WP143 — Priorities redesign: server side, markup and layout.**
  *Suggested model:* Sonnet.
  Goal: the new panel's full server side and markup. The page renders both layouts and switches
  between them. It shows the live summary and status and confirms. Drag and spinner interaction is
  WP144's.
  **Land WP144 right after this, before any deploy.** Until WP144, Priority tiles can't be moved
  and Sum-to-Ten values can't be changed in the browser.
  Deliverables:
  - **Conversion:** a pure function in `engine/build_method.py` mapping five Sum-to-Ten letters to
    the nearest Priority assignment. Sort the categories stably by letter, with display order as
    the tie-break, then hand out A–E in that order. That is exactly optimal for total letter
    distance. Unit tests:
    - all E → display order
    - five distinct letters → unchanged
    - mixed cases
    - a brute-force check over all 120 permutations against a spread of inputs, proving the result
      is minimal and the tie-break holds
  - **Template rewrite** of `_priority_form.html`, following the sketch and the standing rules:
    - The page heading, the method dropdown, then the panel, all in one centred column. The method
      dropdown uses short labels, "Priority" / "Sum-to-Ten". The method explanation moves into the
      explanatory text: one key per method, replacing `Web_Priorities_Intro`.
    - **Priority layout:** the fixed letters A–E in a column of their own. Beside it, a separate
      list of five category tiles in their current order, each with a drag-handle glyph and a
      hidden `<category>_letter` input (Finding 1). The letters must not be inside the tiles,
      because WP144 moves the tiles and the letters stay put.
    - **Sum-to-Ten layout:** one row per category (label, dot leader, value). The value is rendered
      as the markup WP144 will animate: an element with `role="spinbutton"`, `tabindex="0"`,
      `aria-valuemin="0"`, `aria-valuemax="4"`, `aria-valuenow` (points) and `aria-valuetext`
      (e.g. "E, 0 points"), plus ▲/▼ buttons and the hidden `<category>_letter` input. The letter
      → points table reaches the markup as data (`SUM_TO_TEN_POINT_VALUES`), so the script has no
      constants of its own. The ∑ row shows `total / SUM_TO_TEN_TARGET` and gets a highlight
      modifier when it is off target.
    - Below the rows: the Metatype dropdown, then a status line and the [Revert] [CONFIRM] buttons,
      then the summary, then messages (error, stale-selections warning). Messages are at the very
      bottom, per standing rule 1. The status line has a fixed height. Revert's space is always
      reserved.
    - Remove the `<details>`/`<summary>` wrapper (standing rule 3). Keep `#priority-section` as
      the swap target.
  - **Endpoints** (all GET, read-only). GET keeps them clear of the `chargen-changed`/autosave
    middleware and of WP141's origin check, both of which apply to POSTs.
    - **Preview** (e.g. `GET /ui/priorities/preview`, `hx-include` of the form). It renders the
      status line, the CONFIRM/Revert state and the summary for the submitted letters. If the
      Heritage letter changed the metatype offer, it also re-renders the Metatype dropdown out of
      band. Rule for the Metatype dropdown: if the selected metatype is still offered, keep it.
      Otherwise reset to a "Choose metatype" placeholder, and the form is not confirmable. Never
      silently pick a different metatype. The preview must **not** re-render the tiles or the
      spinners: they hold focus and drag state, so swapping them mid-interaction would break it.
    - **Layout switch** (method dropdown change). It re-renders the whole panel in the other
      method's layout. Sum-to-Ten → Priority goes through the conversion function. Priority →
      Sum-to-Ten keeps the letters, except that a never-confirmed character gets all E (see
      "Defaults"). The current metatype is kept by the same rule as the preview.
    - **Revert.** It re-renders the panel from the session's confirmed selection.
  - **Status** (Finding 2):
    - *unconfirmed* means `session.character is None`
    - *confirmed* means the form equals the session's selection; CONFIRM is disabled
    - *changed* means the form differs from it
    - *confirmable* means the letters are valid for the method (Priority: five distinct letters;
      Sum-to-Ten: total equals the target) and a metatype that the Heritage letter offers is
      selected
    - Expose all of it as `data-` attributes on the status element.
  - **Summary** per "Defaults": what each placed priority gives, and "old → new" on changed lines.
    Reuse the data `_priority_form_context` already loads (`heritage_priorities` and the rest,
    i.e. `PriorityTable`).
  - **CSS** in `app.css`, in a "Priorities page" section: the column, the letter and tile grid, the
    tiles, the spinners, the dot leaders, the ∑ highlight, the status line. Theme tokens only.
  - **Tests:**
    - Update the existing priority-form tests for the new markup.
    - New tests for the preview, layout-switch and revert endpoints.
    - The status and confirmable cases.
    - The metatype-reset rule.
    - The never-confirmed all-E rule.
    - Messages render after the controls in document order.
    - The CSP and no-bare-text tests stay green.
  Depends on: nothing new. Read `web/routes/priorities.py` and `_priority_form.html` first.
  Phase W's file covers the shell, if needed.
  Acceptance: pytest is green repo-wide. Every deliverable above is covered server-side. The panel
  renders in both layouts under all four themes, with no CSP violations.

- [x] **WP144 — Priorities redesign: drag-to-reorder and Sum-to-Ten spinners.**
  *Suggested model:* Opus.
  Goal: the client-side widgets on top of WP143's markup.
  Deliverables:
  - **Vendor SortableJS** into `static/vendor/sortablejs/`: a pinned release, its MIT `LICENSE`, a
    `VENDORED.md` with the version, source URL and checksum, matching `vendor/htmx/`. Add an entry
    to `NOTICE`, and include the script in the shell's `<head>` beside htmx. Record in
    `spec/decisions-log.md` that the user approved this front-end dependency on 2026-10-05.
  - **Drag** (in `app.js`): initialise Sortable on the tile list on `htmx:load`. The panel is
    swapped in by navigation, layout switch, revert and confirm, so any new list must get an
    instance, and never a second one on the same list. After each reorder, rewrite every tile's
    hidden input to its row's letter, then dispatch one event that triggers WP143's preview request
    (debounced, e.g. `delay:150ms`). On touch screens, set Sortable's touch delay
    (`delayOnTouchOnly`) so scrolling the page in portrait doesn't start a drag.
  - **Keyboard reordering:** Alt+↑ / Alt+↓ on a focused tile moves it one row, keeps focus on it,
    and runs the same rewrite-and-preview routine. Announce the new position through an
    `aria-live` region.
  - **Spinners:**
    - ▲/▼ buttons and the ↑/↓ arrow keys step the letter (towards A raises it). The value stops at
      A and E, without wrapping.
    - Update the hidden input, `aria-valuenow`/`aria-valuetext` and the visible "E (0)" text.
    - Recompute the ∑ row and its off-target highlight immediately from the point table in the
      markup, so it doesn't wait for the server.
    - Trigger the preview, debounced.
  - **Scroll wheel:** it changes a spinner only when the spinner has focus **and** the wheel event
    is over that spinner. Only then call `preventDefault`, on a listener registered with
    `{ passive: false }`. Wheel up moves towards A. Trap: trackpads send many small `deltaY` events,
    so accumulate deltas and step once per threshold (and treat `deltaMode` line/page units as one
    step each), not once per event.
  - **CONFIRM state:** the server's `data-priority-confirmable` stays authoritative. The script
    may only disable CONFIRM early, while ∑ is off target and before the preview returns. It never
    enables CONFIRM on its own.
  - **Server-side tests:** the vendored file is served and included. The markup hooks the script
    relies on are present in both layouts. CSP tests stay green.
  Depends on: WP143.
  Acceptance:
  - pytest is green.
  - The worklog's manual browser checklist, marked "not run here", covers:
    - mouse drag
    - touch drag on a phone in portrait, with page scroll unaffected
    - keyboard reordering
    - spinner buttons, keys and wheel
    - the wheel ignored when the spinner isn't focused
    - a trackpad producing sane steps
    - ∑ highlight and CONFIRM state
    - the preview updating the summary
    - everything still working after a layout switch, a revert and a confirm (re-initialisation)
    - all four themes

- [x] **WP145 — Priorities redesign: leave-with-unconfirmed-changes dialog.**
  *Suggested model:* Opus.
  Goal: a player can't leave the Priorities page believing unconfirmed edits are in effect.
  Deliverables:
  - **A `<dialog>`** opened with `showModal()`. The text explains that the rest of the character
    still uses the confirmed priorities. Three buttons:
    - **Confirm and continue:** disabled when `data-priority-confirmable` is false.
    - **Stay:** the default focus. Escape does the same.
    - **Revert and continue.**
    For a never-confirmed character there is nothing to revert to. The third button then reads
    "Discard and continue", and Confirm creates the character as usual.
  - **When it fires:** when the panel is in a dirty state and the player is about to remove the
    panel from the page. "Dirty" means status *changed*, or *unconfirmed* after the player has
    touched the form. Cover:
    - htmx requests that replace `#page`: the step-nav links
    - plain links and non-htmx form submissions that leave the page: the title bar's character
      list, account and logout
    - the shell swap after a character switch, if it can be reached from here
    - Not the theme or locale pickers (`/ui/prefs/`), which don't leave the page.
    For reload, closing the tab and typed URLs, a `beforeunload` handler raises the browser's own
    generic prompt. A custom dialog is impossible there. That is accepted.
  - **Trap: the dirty window.** Between a change and the preview's response, the server's status
    attribute is stale. Treat the form as dirty while any change is newer than the last preview
    response. Never conclude "clean" from an out-of-date attribute.
  - **Trap: coexisting with `tabs.js`.** WP138 already handles `htmx:confirm` for the character
    switch warning. Don't let both dialogs fire for one action, and don't break that handler.
  - **Trap: the back button.** htmx history restore isn't cancellable the way a request is.
    Intercept `popstate` while dirty: re-push the current URL, show the dialog, and replay the
    back navigation if the player continues. If that proves unreliable, fall back to
    `beforeunload`-style behaviour, and record the limitation in the worklog. Back must not
    silently discard the edits.
  - **Confirm and continue:** submit the form through htmx. Resume the navigation only on success.
    Have the server signal success explicitly, e.g. an `HX-Trigger: priorities-confirmed` response
    header from `submit_priorities` (WP145: it had to be `HX-Trigger-After-Settle`, since the app
    middleware overwrites `HX-Trigger`); the script must not infer success from the status code. On
    an error, stay, so the error shows at the bottom as usual. WP138's first-confirm path answers
    with a whole-shell swap. Make sure the navigation still resumes (or deliberately lands on the
    new shell) in that case.
  - **Revert and continue:** proceed with the original navigation. Nothing server-side needs
    undoing.
  - **Server-side tests:** the dialog markup and its i18n strings render. `submit_priorities` sends
    the success signal on success and not on error. CSP tests stay green.
  Depends on: WP143, WP144.
  Acceptance:
  - pytest is green.
  - The worklog's manual browser checklist, marked "not run here", covers:
    - each trigger above, in both dirty states
    - no dialog when the form is clean
    - Stay, Escape, Revert and Confirm each doing what they say
    - Confirm disabled when the form isn't confirmable
    - Confirm with a server error staying on the page
    - first-confirm via the dialog
    - the back button
    - reload or close giving the browser prompt
    - no double dialog with the WP138 switch warning

---

#### Redesign 2 — Attributes (WP146)

**Sketch:** `examples/ui/attributes.png` / `.svg`. The table itself doesn't change: same rows, the
same five columns, and the same column headers the page already uses ("Value (augmented)",
"Metatype range"). Only two things change:

- **The one-line budget sentence becomes three boxes** in a row above the table. Each box has a
  small label and a large "remaining/budget" value:
  - **Primary Attributes**, e.g. `20/20`
  - **Special Attributes**, e.g. `9/9`
  - **Karma**, e.g. `25/25`, with a subtitle "(5 x level)"
- **The Update Attributes button goes.** The sketch draws it full-width at the bottom. The user
  then ruled to drop it (below).

**The user's rulings (2026-10-06):**

| Question | Ruling |
|---|---|
| Update Attributes button | **Dropped. Autosave only.** The form already posts on every `change` and on `number-input` (400 ms debounce), so the button has never done anything extra. No explicit-commit model, no leave dialog: an attribute edit takes effect as soon as it posts, as it does today. |
| What "(5 x level)" under Karma means | A **cost hint**: raising an attribute with Karma costs the new rating × 5 (core rulebook p. 106-107, Karma Advancement Table; `ATTRIBUTE_KARMA_PER_RATING` in `engine/character.py`, cited in `learnings/phase-o.md`'s WP51 entry). The box still shows the same leftover Karma remaining / available as today's sentence (`attribute_karma_remaining` / `attribute_karma_budget`). It is not a fixed 25. |
| A pool overspent (remaining < 0) | **That box is highlighted**, with the same treatment as the Sum-to-Ten ∑ row. The explaining warning stays at the bottom (standing rule 1). |
| The boxes in portrait | **They stay in one row and shrink**: three equal columns, with the labels wrapping inside the boxes. |

**Defaults this file sets (not user rulings; change them here if they turn out wrong):**

- **One "Special Attributes" label** for mundane and Awakened characters alike, as the sketch
  shows. Today's two sentences ("Special (Edge)" / "Special (Edge/Magic)") become one label. The
  rows below already show which attributes the pool covers. The magic-specific variant's i18n key
  is removed if nothing else uses it.
- **A plain page heading** ("Attributes", `Label_Attributes`) above the boxes, as on the
  Priorities page. The sketch doesn't show one. Standing rule 3 keeps the heading and drops only
  the `<details>` wrapper.
- **The column cap is wider than Priorities' 30rem**, because the table has five columns. Pick
  the narrowest cap at which the table fits without horizontal scroll at its widest localised
  header (about 36–40rem). Below that width the column fills the pane, per standing rule 2. If
  the table still overflows on a phone, wrap just the table in an `overflow-x: auto` container.
  The boxes and the page must never scroll sideways.

---

- [x] **WP146 — Attributes redesign: budget boxes, autosave only.**
  *Suggested model:* Sonnet. No new client behaviour: the existing `number-input` hook in
  `app.js` keeps driving autosave. Everything is markup, CSS and pytest.
  Goal: the Attributes page as sketched in `examples/ui/attributes.png`, with the user's rulings
  above.
  Deliverables:
  - **Template rewrite** of `_attribute_allocation.html`:
    - Drop the `<details>`/`<summary>` wrapper (standing rule 3). The heading becomes a plain
      heading. Keep `#attribute-allocation` as the swap target. `test_web_shell.py` and
      `session.py` reference it.
    - **Three budget boxes** in one row, above the table. Each box has a label and a
      `remaining/budget` value. The Karma box adds the "(5 x level)" subtitle. An overspent box
      (remaining < 0) gets a highlight modifier class, decided in the template from the context
      values the route already computes. The script decides nothing.
    - **Remove the submit button** and the `Web_Attributes_Update` key. The form keeps
      `hx-trigger="change, number-input delay:400ms"`. Check that pressing Enter in a number
      input still does nothing harmful. With several fields and no submit button, a browser does
      no implicit submission. If one ever happens, it has no `action` and would GET the current
      URL, so add an explicit guard if a test shows otherwise.
    - **Messages at the bottom** (standing rule 1): `attribute_error` and
      `attribute_budget_warning` move below the table, inside a region that doesn't push the
      table. The table is the last control on the page, so placing them after it is enough.
    - The no-character placeholder branch stays as it is, apart from losing the wrapper.
  - **i18n** (standing rule 6): new keys for the three box labels and the Karma subtitle. Look
    for legacy keys with exactly matching English before adding new ones. Retire
    `Web_Attributes_PrimaryRemaining`, `Web_Attributes_SpecialRemaining`,
    `Web_Attributes_SpecialMagicRemaining`, `Web_Attributes_KarmaRemaining` and
    `Web_Attributes_Update` if nothing else uses them.
  - **CSS** in `app.css`, in a new "Attributes page (WP146, Phase Z)" section after the
    Priorities one:
    - the centred column (see "Defaults" for the cap)
    - the box row: three equal columns that stay in one row at every width, with labels wrapping
    - the boxes: solid border, small label, large tabular-numeral value
    - the overspent highlight: reuse the ∑ row's off-target treatment, or share one class with it
    - Theme tokens only. Check all four themes, in light and dark (standing rule 5).
  - **Trap: focus across the autosave swap.** Every autosave replaces `#attribute-allocation`
    with `outerHTML`. htmx only restores focus and caret to an element that has a stable `id`.
    Without one, a player typing "4" and pausing loses focus mid-edit. Check whether the current
    inputs keep focus. If they don't, give each input a stable `id` (e.g. `attr-BOD`,
    `karma-attr-BOD`) so htmx's focus preservation applies. Cover the ids with a test.
  - **Tests:**
    - Update the existing attribute-page tests (sentence wording, the button) for the new markup.
    - New tests:
      - three boxes, each showing the right `remaining/budget`, for a mundane and an Awakened
        character
      - the overspent modifier present exactly when remaining < 0, per pool
      - no submit button
      - messages after the table in document order
      - no `<details>` wrapper
    - The CSP and no-bare-text tests stay green.
  Depends on: nothing new. Read `web/routes/attributes.py`
  (`_attribute_allocation_context`) and the WP143 section of `app.css` first, for the column and
  highlight idiom.
  Acceptance:
  - pytest is green repo-wide, and every deliverable above is covered server-side.
  - The worklog has a short manual browser checklist, marked "not run here":
    - the boxes under all four themes, light and dark
    - portrait width: the boxes in one row, no sideways page scroll
    - the overspent highlight
    - typing a two-digit value without losing focus
    - autosave still applying edits (the value column updates)

---

#### Redesign 3 — Qualities (WP147)

**No sketch.** Raised 2026-10-17 as "redesign the Qualities page in the same style as the
Attributes and Priorities pages". This block applies the standing rules and WP146's budget-box
idiom to today's page (`_quality_selection.html`). If the user sketches the page later, the sketch
overrides the defaults below.

Today's page, top to bottom: a `<details>` wrapper, the error and budget warning **above** the
controls (breaks standing rule 1), the "free from metatype" line, a two-sentence Karma summary,
then one 6-column table of all ~96 offered qualities, Positive and Negative interleaved (Select,
Quality, Category, Karma, Rating, Detail). The Mentor Spirit fieldset follows, then an "Update"
button. The form already autosaves (`hx-trigger="change, number-input delay:400ms"`), so the
button does nothing extra. This is the same situation WP146 found on Attributes.

**The user's rulings (2026-10-17, after WP147 first landed):**

| Question | Ruling |
|---|---|
| Positive and Negative on one page | **A dropdown switches between them**, like the Priorities method dropdown. One category's table shows at a time. This replaces the two stacked sections below. |

**Defaults this file sets (not user rulings; change them here if they turn out wrong):**

- **Two budget boxes replace the Karma sentence**, using the Attributes-page box style:
  **Positive Qualities** and **Negative Qualities**, each showing `remaining/limit` against
  `QUALITY_KARMA_LIMIT` (25, core rulebook Step Four: Purchase Qualities). Remaining is limit − spent, as on Attributes.
  An overspent box (remaining < 0, reachable on an error echo) takes the overspent highlight.
  The two boxes stay in one row at every width.
- **The Update button goes; autosave only.** This follows the user's Attributes ruling
  (2026-10-06): the button never did anything extra, so there is no explicit commit and no leave
  dialog.
- **The table splits into two sections, Positive then Negative**, each under its own small
  heading. *(Superseded by the dropdown ruling above: the dropdown replaces the headings, and the
  page opens on Positive. The view isn't remembered across page visits.)* The Category column goes, because the section says it. That leaves five columns:
  Select, Quality, Karma, Rating, Detail. The order inside each section stays as it is today. No
  search or filter box: that is client behaviour, and the user hasn't asked for it.
- **The "free from metatype" line stays** under the boxes. It only changes when the metatype
  changes on the Priorities page, so it never moves a control while the player works here.
- **The Mentor Spirit fieldset stays where it is**, below the tables (shown only with Positive), with its markup unchanged
  apart from stable ids (see the trap below). It is the last control on the page.
- **A plain page heading** ("Qualities", `String_Qualities`) above the boxes, as on the other two
  redesigned pages.
- **Column cap:** the same as Attributes (40rem) if the five-column table fits at its widest
  localised header. Otherwise use the narrowest cap that fits. On a phone, wrap each table in an
  `overflow-x: auto` container. The boxes and the page must never scroll sideways.

---

- [x] **WP147 — Qualities redesign: budget boxes, split table, autosave only.**
  *Suggested model:* Sonnet. No new client behaviour: the existing autosave triggers keep driving
  the form. Everything is markup, CSS and pytest.
  Goal: the Qualities page restyled like the Attributes page, per the defaults above.
  Deliverables:
  - **Template rewrite** of `_quality_selection.html`:
    - Drop the `<details>`/`<summary>` wrapper (standing rule 3). The heading becomes a plain
      heading. Keep `#quality-selection` as the swap target, and grep for other references to it
      (`test_web_shell.py`, `session.py`) before touching it.
    - **Two budget boxes** in one row above the table(s), with a highlight modifier for an
      overspent pool. Decide it in the template from context values. Add `positive_remaining` /
      `negative_remaining` to `_quality_selection_context` if that keeps the template simple.
    - **Two table sections**, Positive then Negative, without the Category column. Split
      `quality_rows` server-side (e.g. `positive_rows` / `negative_rows` in the context) rather
      than filtering in Jinja. Keep every input name exactly as it is (`quality_id`,
      `quality_rating_<key>`, `quality_choice_<key>`, `quality_text_<key>`), so
      `_submitted_picks` and `submit_qualities` need no change. Repeatable qualities keep their
      "add another" rows inside their own section.
    - **Remove the submit button.** Same Enter-key check as WP146: with several fields and no
      submit button there is no implicit submission. Add a guard only if a test shows otherwise.
    - **Messages at the bottom** (standing rule 1): `quality_error` and `quality_budget_warning`
      move below the Mentor Spirit fieldset, i.e. after the last control.
    - The no-character placeholder branch stays as it is, apart from losing the wrapper.
  - **Trap: focus across the autosave swap.** This is the exposure the WP146 decisions-log entry
    flagged for every autosaving step form. Every autosave replaces `#quality-selection` with
    `outerHTML`, and htmx only restores focus and caret to an element with a stable `id`. The
    Detail text box is the worst case: a player typing a name pauses and loses focus mid-word.
    Give every input and select a stable `id` derived from its row key (e.g. `quality-<key>`,
    `quality-rating-<key>`, `quality-choice-<key>`, `quality-text-<key>`, and fixed ids for the
    mentor fields). Row keys contain `:` for repeat instances (`_row_key`), so make sure the
    derived id is valid and unique. Replacing `:` with `-` is fine as long as it can't collide.
    Cover the ids with a test.
  - **i18n** (standing rule 6): new keys for the two box labels and the two section headings.
    Look for legacy keys with exactly matching English first: legacy
    `String_SelectQuality_XPathQuery_PositiveOnly` / `…_NegativeOnly` read "Positive Qualities" /
    "Negative Qualities", and could serve as the box labels or the section headings. Retire `Web_Qualities_PositiveKarma`,
    `Web_Qualities_NegativeKarma`, `Web_Qualities_Update` and `Web_Qualities_ColCategory` if
    nothing else uses them (check `_character_sheet.html`).
  - **CSS** in `app.css`, in a new "Qualities page (WP147, Phase Z)" section after the Attributes
    one. Reuse the Attributes box classes rather than copying them: if they're page-specific
    (`.attribute-budget…`), rename them to a shared name (e.g. `.budget-box…`) and update the
    Attributes template and tests in the same commit. Section headings, the column cap and the
    table wrapper go in the new section. Theme tokens only. Check all four themes, light and dark
    (standing rule 5).
  - **Tests:**
    - Update the existing quality-page tests for the new markup (Karma sentence, the button, the
      Category column).
    - New tests:
      - two boxes, each with the right `remaining/limit`, including after picking a positive and
        a negative quality
      - the overspent modifier present exactly when a pool's remaining < 0
      - Positive rows only in the Positive section and Negative rows only in the Negative one,
        with a repeatable quality's "add another" row in the right section
      - no submit button, no `<details>` wrapper
      - messages after the last control in document order
      - stable, unique ids on the inputs, including repeat instances
      - posting the unchanged form names still commits the same selection (POST contract
        unchanged)
    - The CSP and no-bare-text tests stay green.
  Depends on: nothing new. Read `web/routes/qualities.py` (`_quality_rows`,
  `_quality_selection_context`), the WP146 template `_attribute_allocation.html` and the WP146
  section of `app.css` first.
  Acceptance:
  - pytest is green repo-wide, and every deliverable above is covered server-side.
  - The worklog has a short manual browser checklist, marked "not run here":
    - the boxes and section headings under all four themes, light and dark
    - portrait width: the boxes in one row, no sideways page scroll
    - the overspent highlight
    - typing a Detail text and a rating without losing focus
    - autosave still applying edits (boxes update on check/uncheck)
    - the Mentor Spirit fieldset still working for a magic-active character
    - the Attributes page unchanged if the box classes were renamed

---

#### Redesign 4 — Skills (WP148-150)

**Sketch:** `examples/ui/skills.png` / `.svg`. It shows three states of one page:

- **A strip of angled tabs across the top.** In order: Combat, Physical, Social, Technical,
  Vehicle, Group, Magical, Resonance, Knowledge, Language, Special. The tabs sit at the left. The
  green area to their right is filler that grows with the window, so the tabs never spread out.
  Point counters sit at the strip's two ends: "S 36/36" and "G 5/5" at the top left, and a
  counter at the bottom right of the filler.
- **A category tab** (Physical shown) has a table: Skill, Attribute, Group, S pts, K pts, Rating,
  Specialization, Pool. The Specialization cell is a **toggle followed by a text field**. The toggle
  chooses whether the specialization is bought with skill points or with Karma.
- **The Group tab** has a table: Group Name, Components (the member skills), S pts, K pts, Rating.
- **The Special tab** (exotic skills) has a table: Skill, Attribute, Detail (a text field), S pts,
  K pts, Rating, Pool. It has no Specialization column. An **Add Special Skills** button sits above
  the bottom button.
- Each state ends with a full-width **Update Skills** button.

Today's page has two sub-tabs (WP98), "Active Skills" and "Knowledge & Languages". Each holds a
stack of collapsible sections, plus a filter box and a "rated only" checkbox. This redesign
replaces both sub-tabs with the single tab strip.

**The user's rulings (2026-10-25):**

| Question | Ruling |
|---|---|
| Counters | **Four:** S (skill points), G (skill group points), **Ka** (Karma), **Kn** (free Knowledge points). Ka and Kn sit together at the strip's right end, where the sketch draws its one "K" counter. The sketch's "K" meant Knowledge. |
| Group tab's points header | Spelled out as **Group Points**. The sketch's "S pts" there is a sketch shorthand. |
| Knowledge & Languages | **Folds into this page as one Knowledge tab** covering both (ruled the same day). Knowledge and Language skills work the same way apart from Native, so the sketch's separate Language tab goes. The old sub-tab goes too. |
| Portrait | **The tab strip becomes a dropdown** below a breakpoint. Its order is the tab order, so the main skill categories come first, then Group, then the rest. |
| Update Skills button | **Dropped. Autosave only**, as on Attributes and Qualities. |
| Add Special Skills button | **Kept.** It is how an exotic skill gets added. |
| Magical tab for a Mundane character | **Always enabled.** Arcana is a Pseudo-Magical skill that a mundane character may learn, so for a Mundane character the tab holds Arcana alone. An Awakened character sees every magical skill they may buy (WP118's Adept rules unchanged). This **reverses WP61's ruling** that Arcana needs an Awakened character. See the decisions log, 2026-10-25. |
| Resonance tab | **Disabled for a non-Technomancer**, and visible so the tabs after it never move. Technomancers are out of scope (Project Overview), so in practice it is always disabled. It carries a disabled reason, the same way the nav's Resonance entry does. |
| Filter and "rated only" | **Two more tabs, after Special:** a **Filtered** tab, which takes a filter string and shows the matching skills, and a **Rated** tab, which shows every skill with a rating. They replace today's filter box and checkbox. |
| Text-field placeholders | **Every text field's placeholder is specific to its row.** Today every field shows the same "e.g. Axes". |

**Defaults this file sets (not user rulings; change them here if they turn out wrong):**

- **The tab is a server-rendered link, like WP98's sub-tabs.** Each tab is
  `GET /ui/page/skills/<tab>`, with htmx into `#page` and pushed to history. All three of WP98's
  constraints still hold (decisions log, 2026-09-24, WP98):
  - Every fragment is still rendered.
  - A tab switch is a fresh render.
  - The strip re-fetches on `chargen-changed`.
  
  The counters live in the strip, so they refresh the same way. This also covers a Knowledge
  autosave changing S (Knowledge spending Active points, WP125). Each form carries a hidden
  `skills_tab` field, so a fragment re-rendered after autosave shows the same tab. Inactive panels
  are rendered but `hidden`, as on Qualities, so every autosave still posts every row. The old `active` sub-tab slug stays valid as an alias for
  Combat. `knowledge` is still the Knowledge tab's slug.
- **Tab slugs and order:**
  - `combat`, `physical`, `social`, `technical`, `vehicle`: skill categories Combat, Physical,
    Social, Technical and Vehicle Active
  - `group`
  - `magical`: Magical Active plus Pseudo-Magical Active
  - `resonance`
  - `knowledge`: Knowledge and Language skills in one table
  - `special`: the exotic skills
  - `filtered`, `rated`
  
  The page opens on Combat. The current tab is not remembered between page visits beyond the URL.
- **Counter figures** come from the same values as the resource panel's rows (`shell.py`, the
  resource rows built in `chargen_context`). Ka is the character's leftover Karma, using the
  resource panel's Karma figures. Each counter reads `remaining/budget`. A counter with
  remaining < 0 takes the overspent highlight, decided in the template. In portrait, the four
  counters sit in one row above the dropdown.
- **The specialization toggle**, worked out on the server:
  - **Form fields:** one text field `spec_<id>` and one checkbox `spec_karma_<id>`, where checked
    means Karma. The route maps the text into `specializations` or `karma_specializations`. The
    engine's rule of at most one specialization per skill
    (`chummer5.engine.skills`, the "already has a specialization" check) is then met by
    construction.
  - **Points need a points-bought rating.** A specialization may use skill points only when the
    skill has at least 1 skill point of its own (p. 129 needs a rating first; p. 88 forbids
    specializing a grouped skill in Step Five). Otherwise the toggle renders checked and disabled. A disabled checkbox doesn't
    post, so a hidden `spec_karma_<id>` carries the value.
  - **Exotic skills** have no specialization (WP124), so their rows get no toggle.
  - **Knowledge rows (Language included)** get the same toggle, using Knowledge points or Karma
    (WP125).
- **The Group tab's Components** are the member skills' names, translated and joined with
  `Web_List_Separator`, in catalog order. The group shows up only where `offered_skill_groups`
  already offers it.
- **Knowledge tab: one table for Knowledge and Language skills.** Columns: Name (text), Category
  (select: the four knowledge categories plus **Language**, as legacy `skills.xml` already treats
  it), Attribute (the category's linked attribute, display only), Native, Kn pts, Ka pts, Rating,
  Specialization (toggle and text), Pool.
  - **Native** is a checkbox that is enabled only on a Language row. The cell is always there, so
    changing a row's category never moves a control. Turning a Language row into another category
    drops its Native flag.
  - **The form posts one set of row fields** (`knowledge_*_<i>`). `submit_knowledge` sorts each
    row into a `KnowledgeSkillPick` or a `LanguageSkillPick` by its category, so the engine's two
    lists and their validation stay unchanged. That includes the native-language limit.
  - **The row cap** is `MAX_KNOWLEDGE_ROWS + MAX_LANGUAGE_ROWS`, counted together.
  - **Today's explanatory sentences** (examples per category, suggested languages) shrink to one
    short help line. The examples move into the placeholders.
- **Add rows with a button on every list the player types into.**
  - **Special:** the Add Special Skills button posts the form with `exotic_add=1`. The response
    shows one new add row (skill select, Detail, S pts, Ka pts). As today, the row is committed
    once it names a skill, a detail and some points.
  - **Knowledge** gets the same idiom ("Add Knowledge Skill"): filled rows plus one blank row
    per press, up to the combined cap. At the cap the button is disabled, and its space is always
    reserved (standing rule 1).
- **The Filtered tab** has a text field at the top of the panel. Every category section that
  holds a matching row is shown under its own small heading, with its own column set. That covers
  the active categories, Special and Knowledge, but not Group. Sections without a
  match are hidden. Matching is client-side (the existing `applySkillFilter` idea in `app.js`, on
  the translated name plus the exotic detail), and the query survives an autosave swap through
  the existing filter store.
- **The Rated tab** uses the same section layout and shows every skill with a rating above 0.
  **The row set is fixed when the tab opens.** A row the player sets to 0 stays visible until they
  leave the tab, so rows don't vanish under the cursor while the player edits (standing rule 1).
  The script stores the visible row keys on tab entry and reapplies them on `htmx:load`.
- **Placeholders**, all in the form "e.g. …" (one new key with an `{example}` argument), with the
  example translated through the same `dterm` lookup as the skill names and falling back to
  English:
  - **Active skill specialization:** the skill's first suggested specialization
    (`Skill.specializations`, which every non-exotic active skill has).
  - **Special Detail:** the base skill's first suggested specialization. Exotic Melee Weapon has
    none in the data, so it uses its own i18n example (a monofilament whip).
  - **Knowledge name** (blank row): an entry from `skills.xml`'s `<knowledgeskills>`, chosen by
    row index so neighbouring rows differ. If the row's category is already set, the entry comes
    from that category.
  - **Knowledge specialization:** the first suggested specialization of the catalog entry whose
    name matches the row's name, ignoring case.
  - **An unmatched Language row** uses Read/Write, because every catalog language has Read/Write,
    Speak and a dialect.
  - **Any other freeform name with no match gets no placeholder**, because an example borrowed
    from another skill would mislead.
  - `Web_Skills_SpecPlaceholder` and `Web_Skills_ExoticSpecificPlaceholder` are retired.
- **Column cap:** Category tabs have eight columns, so this page gets the widest cap so far. Pick
  the narrowest cap at which a category tab's table fits without sideways scrolling at its widest
  localised header. On a phone each table goes in an `overflow-x: auto` wrapper. The strip,
  counters and page never scroll sideways.
- **The angled tabs** are CSS: a skewed tab shape with the label rotated inside it. Each tab is a
  real link and can be focused. The current tab has `aria-current="page"`, and the disabled
  Resonance tab is a `<span>` with its reason, as on WP98's strip.

---

- [x] **WP148 — Skills redesign: tab strip, counters, active-skill tabs, specialization toggle.**
  *Suggested model:* Opus. It reworks the composite-page mechanism for one page and changes the
  skills POST parsing.
  Goal: the Skills page as sketched in `examples/ui/skills.png`, for every tab except Knowledge,
  Filtered and Rated. Those three are WP149 and WP150. Until WP149, the Knowledge tab shows
  today's `_knowledge_skills.html` unchanged.
  Deliverables:
  - **Tab mechanism.** The skills `StepPage` gets the strip and slugs from "Defaults". Read
    `shell.py`'s `StepPage`/`PageSection`, `_page.html`, the tab-strip route
    `GET /ui/tabs/{slug}` and the WP98 decisions-log entry first. Then either extend those types
    so a page can have tabs that aren't one fragment each, or give the skills page its own strip
    template. Pick whichever keeps the other composite pages untouched. The `active` alias keeps
    working. The about 38 composite-page test requests stay green.
  - **Counters** S, G, Ka and Kn, placed as in "Defaults", with the overspent highlight. They
    refresh with the strip on `chargen-changed`.
  - **Template rewrite** of `_skill_allocation.html`:
    - Drop the `<details>` wrapper and the per-category `<details>` (standing rule 3). Keep
      `#skill-allocation` as the swap target.
    - **One panel per tab:** five category panels, Magical, Resonance (rendered empty when
      disabled), Group and Special. Only the current one is shown, and the rest are `hidden` but
      still in the form. A hidden `skills_tab` input carries the tab through autosave.
    - **Category panels:** Skill, Attribute, Group, S pts, Ka pts, Rating, Specialization (toggle
      and text), Pool. Rating and Pool are displayed exactly as today.
    - **Group panel:** Group Name, Components, Group Points, Ka pts, Rating. Input names
      (`group_<name>`, `karma_group_<name>`) are unchanged.
    - **Special panel:** today's exotic instance rows, plus the add row the **Add Special Skills**
      button reveals. The button is `type="button"` and posts through htmx with `exotic_add=1`,
      not a native submit. The 2026-09-24 decisions-log entry found that these forms' `hx-trigger`
      replaces htmx's `submit`. The input names (`exotic_key`, `exotic_new_*`) are unchanged.
    - **Remove the Update button,** the filter box and the "rated only" checkbox. The last two
      come back as tabs in WP150. Do the same Enter-key check as WP146.
    - **Messages at the bottom** (standing rule 1): `skill_error` and `skill_budget_warning` go
      below the current panel, outside anything that can push a control.
    - **Stable ids** on every input: `skill-<id>`, `karma-skill-<id>`, `spec-<id>`,
      `spec-karma-<id>`, `group-<slug>` and so on. Exotic instance keys contain `|`, so map them to
      a valid id that can't collide.
  - **Specialization toggle** as in "Defaults": parse `spec_<id>` and `spec_karma_<id>` in
    `submit_skills`, use the hidden fallback for the forced-Karma case, and decide in
    `_skill_allocation_context` whether the toggle is forced. `parse_specializations`'s other
    callers are unchanged.
  - **Arcana for Mundane characters:**
    - `offered_skills` offers Pseudo-Magical Active skills to every character. Magical Active
      skills still need an Awakened character, matching legacy's `SkillsSection.cs` filter, which
      gates only "Magical Active".
    - Update the WP61 comment in `catalogs.py` to point at the 2026-10-25 decisions-log entry.
    - Check that `skill_purchase_rules` doesn't block Arcana for a mundane character, and that
      `MUNDANE_SKILL_GROUPS` doesn't change (Arcana has no group).
    - The free magic skill grant (`MAGICAL_SKILL_CATEGORIES`) is unaffected.
  - **Placeholders** for the active-skill specialization fields and the Special Detail field, as in
    "Defaults". Retire both old placeholder keys once WP149 no longer uses them. Until then, keep
    `Web_Skills_SpecPlaceholder` for the knowledge fragment.
  - **i18n** (standing rule 6): tab labels, counter labels, column headers, the toggle's
    accessible label (one each for points and Karma), the Add button and Resonance's disabled
    reason. Check legacy keys first, since `Web_Nav_ResonanceUnsupported` may fit. Retire
    `Web_Skills_PointsRemaining`, `Web_Skills_GroupPointsRemaining`, `Web_Skills_KarmaRemaining`,
    `Web_Skills_Update`, `Web_Skills_Filter*`, `Web_Skills_RatedOnly`,
    `Web_Skills_ColKarmaSpec` and the help sentences the panels no longer show, if nothing else
    uses them.
  - **CSS** in a new "Skills page (WP148, Phase Z)" section of `app.css`: the angled strip and
    filler, the counters (sharing the overspent treatment with `.budget-box`), the toggle switch,
    the column cap and table wrappers. Use theme tokens only, and check all four themes in light
    and dark. The portrait dropdown is WP150. Until then, let the strip scroll sideways inside
    its own container below the breakpoint, never the page.
  - **Tests:**
    - Update the existing skills-page tests for the new markup.
    - New tests:
      - each tab slug renders its panel visible and the others hidden, and `active` aliases
        `combat`
      - the Magical tab enabled for a Mundane character with only Arcana; a mundane character can
        post Arcana points and commit them
      - Resonance disabled, with its reason
      - the counters' values and overspent modifiers
      - the toggle: points and Karma both commit to the right engine field, and it is forced to
        Karma when the skill has no skill points of its own
      - the Group panel's Components
      - Add Special Skills reveals the add row, and filling it commits an instance (the WP124
        tests keep passing)
      - the per-skill placeholders
      - no submit button and no `<details>`
      - messages after the panel
      - stable unique ids, including exotic instances
      - `skills_tab` surviving an autosave
    - The CSP and no-bare-text tests stay green.
  Depends on: nothing new. Read `web/routes/skills.py`, `catalogs.py` (`offered_skills`), the WP98
  decisions-log entry and the WP147 template and CSS first.
  Acceptance:
  - pytest is green repo-wide, and every deliverable above is covered server-side.
  - The decisions log has the Arcana entry.
  - The worklog has a manual browser checklist, marked "not run here":
    - the strip under all four themes, light and dark, at a wide window (filler grows, tabs stay
      left)
    - tab switching and history back
    - the toggle's look and behaviour
    - typing a specialization without losing focus
    - Add Special Skills
    - autosave updating Rating, Pool and the counters

- [x] **WP149 — Skills redesign: Knowledge tab (Knowledge and Language skills).**
  *Suggested model:* Sonnet. Markup, parsing and tests on the knowledge fragment, inside WP148's
  mechanism.
  Goal: Knowledge & Languages folded into the Skills page's single Knowledge tab, as in
  "Defaults".
  Deliverables:
  - **Template rewrite** of `_knowledge_skills.html`:
    - One panel holding the merged table, shown only on the Knowledge tab. Keep
      `#knowledge-skills` as its swap target, and add the hidden `skills_tab` input.
    - The table is as in "Defaults", with Language as a category and Native enabled only on
      Language rows.
    - Filled rows plus one blank row, with an "Add Knowledge Skill" button (`type="button"`,
      posted through htmx). At the cap the button is disabled and its space is kept.
    - **Merged parsing:** `submit_knowledge` reads one row series (`knowledge_name_<i>`,
      `knowledge_category_<i>`, `knowledge_native_<i>`, the points, Karma, `knowledge_spec_<i>`
      and `knowledge_spec_karma_<i>`) and sorts each row by its category into the existing
      knowledge and language picks. Read `_parse_knowledge_skills`, `_parse_languages` and the
      `_by_name` helpers first: Karma points and specializations are keyed by name today, so make
      sure a knowledge skill and a language with the same name can't collide. The `language_*`
      field names are retired. Saved characters are unaffected, because the engine types don't
      change.
    - Rows on the page keep a stable order (`ChargenSession` order, knowledge then languages, as
      today), so a row's index, and with it its id, doesn't shift when its category changes.
    - Remove the Update button and the `<details>` wrapper.
    - Messages go at the bottom.
    - Stable ids from the row index.
  - **Its budget sentence goes.** Kn and Ka are WP148's counters. Active points spent on
    Knowledge show up in S, and a short line in the Knowledge panel states how many Active points
    Knowledge is using.
  - **Retire the sub-tab.** Remove the `knowledge` `PageSection` and `Web_Tab_KnowledgeLanguages` /
    `Web_Tab_ActiveSkills` if nothing else uses them. The `knowledge` slug stays as an alias for
    the Knowledge tab.
  - **Placeholders** for names and specializations as in "Defaults". Read
    the knowledge catalog from `skills.xml`'s `<knowledgeskills>` (add a loader beside
    `load_skills` if none exists). Then retire `Web_Skills_SpecPlaceholder`.
  - **i18n** for the new labels and buttons. Retire `Web_Knowledge_FreeRemaining`,
    `Web_Knowledge_ActivePointsUsed`, `Web_Knowledge_KarmaRemaining`, `Web_Knowledge_Update`
    and the help sentences the panels no longer show, if unused (check `_character_sheet.html`).
  - **Tests:**
    - Update the knowledge-page tests.
    - New tests:
      - the merged table's columns, with Native enabled only on Language rows
      - a row switched between Language and another category committing to the right engine list
      - the native-language limit still enforced
      - the Add button and the combined cap
      - the toggle committing to the right field for a knowledge skill and a language
      - the placeholders, including a matched and an unmatched knowledge name
      - S dropping when Knowledge spends Active points (WP125), seen in the counter after the
        strip re-fetches
      - stable ids
      
  Depends on: WP148.
  Acceptance:
  - pytest is green repo-wide.
  - The worklog has a manual browser checklist, marked "not run here":
    - the tab under the four themes
    - adding rows up to the cap
    - switching a row to and from Language
    - typing a name without losing focus
    - the counters updating after a Knowledge edit

- [x] **WP150 — Skills redesign: Filtered and Rated tabs, portrait dropdown.**
  *Suggested model:* Sonnet. Small client behaviour in `app.js`. Everything else is markup and CSS.
  Goal: the two view tabs and the portrait layout, as in "Defaults".
  Deliverables:
  - **Filtered and Rated tabs** after Special. Both show every section except Group, each under
    its own small heading:
    - **Filtered:** a filter text field. The script hides rows that don't match and sections left
      empty. Rework `applySkillFilter`/`restoreSkillFilter` to the new markup. Rows carry
      `data-skill-name` and `data-skill-rating` from the server, including Knowledge rows.
    - **Rated:** the row set is fixed when the tab opens, then reapplied on `htmx:load`. It is
      reset when the player leaves the tab and comes back.
  - **Portrait dropdown.** Below the breakpoint, the strip is replaced by a `<select>` of the same
    tabs in the same order, with Resonance disabled. Changing it navigates to that tab's URL
    (from `app.js`, or with htmx attributes, but no inline script). Above the breakpoint the
    select is hidden, and below it the strip is hidden. Pick the breakpoint where the strip stops
    fitting.
  - **i18n** for the two tab labels and the filter field's label and placeholder.
  - **Tests:** both tabs render all sections with the data attributes, the dropdown lists every tab
    with the right `selected` and disabled entries, and the CSP tests stay green.
  Depends on: WP149.
  Acceptance:
  - pytest is green repo-wide.
  - The worklog has a manual browser checklist, marked "not run here":
    - filtering across active, Special and Knowledge
    - the query surviving an autosave
    - a rated row set to 0 staying until the player leaves the tab
    - portrait: the dropdown, no sideways page scroll, the counters in one row
    - the four themes, light and dark
