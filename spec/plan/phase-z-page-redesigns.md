[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase Z — Post-MVP: page redesigns (WP143-145, open-ended)

**Why now.** Raised 2026-10-05 with a hand-drawn redesign of the Priorities page
(`examples/ui/priorities.png` / `.svg`, committed alongside this file). Phase W (WP97-106) built the
application shell and moved every step into it *unchanged*. Each step's contents are still the
pre-shell accordion forms. This phase is where individual pages get redesigned for the shell, one
sketch at a time.

**This phase is open-ended.** More page redesigns are likely to follow. **Add each one here** as
its own block of WPs, with its sketch under `examples/ui/` and a dated rulings table like the
Priorities one below. Don't open a new phase per page. Claim WP numbers from the index's "Next
unclaimed WP number" as usual, and update the "WP143-145" range in this file's title and in the
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

- [ ] **WP144 — Priorities redesign: drag-to-reorder and Sum-to-Ten spinners.**
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

- [ ] **WP145 — Priorities redesign: leave-with-unconfirmed-changes dialog.**
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
    header from `submit_priorities`; the script must not infer success from the status code. On
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
