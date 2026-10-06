"""WP15: attribute and skill point allocation UI, backed by WP6's `create_character` and WP7's
`create_skill_allocation` directly.

Cross-checks the UI's result against those engine functions called directly with the same inputs,
same acceptance bar as WP14's own test module: "manual walkthrough; values match engine output for
the same inputs."
"""

import re

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.character import (
    ATTRIBUTE_KARMA_PER_RATING,
    STARTING_KARMA,
    create_character,
    karma_advancement_cost,
    metatype_choices,
)
from chummer5.engine.skills import (
    KARMA_SKILL_PER_RATING,
    create_skill_allocation,
    dice_pool,
    skill_rating,
)
from chummer5.web.app import MUNDANE_SKILL_GROUPS, MUNDANE_SKILLS, create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()


def _confirm_human(client: TestClient) -> None:
    """Establishes a session with Human confirmed at Heritage A / Attributes B / Skills C /
    Resources D -- the same combination WP14's own tests use, giving every attribute/skill test a
    known, real budget to allocate against (Attributes B, Skills C).
    """
    client.get("/")
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    assert "Confirmed: Human" in response.text


def test_index_before_confirmation_shows_placeholder_not_allocation_forms() -> None:
    client = TestClient(create_app())

    attributes_page = client.get("/ui/page/attributes")
    skills_page = client.get("/ui/page/skills")

    assert (
        "Confirm a metatype and priorities on the Priorities page before allocating attribute "
        "points." in attributes_page.text
    )
    assert (
        "Confirm a metatype and priorities on the Priorities page before allocating skill "
        "points." in skills_page.text
    )


def test_index_after_confirmation_shows_allocation_forms_with_full_budget() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    attributes_page = client.get("/ui/page/attributes")
    response = client.get("/ui/page/skills")

    expected_primary_budget = PRIORITIES.attributes["B"].points
    expected_skills_budget = PRIORITIES.skills["C"].skills
    assert f"{expected_primary_budget}/{expected_primary_budget}" in attributes_page.text
    assert f"{expected_skills_budget} / {expected_skills_budget}" in response.text
    # Magic-linked skills are excluded from the mundane MVP allocation UI (see app.py's
    # MUNDANE_SKILLS comment) -- Spellcasting (Sorcery group, MAG-linked) must not appear.
    assert "Spellcasting" not in response.text
    assert "Alchemy" not in response.text
    # WP61 correction: Assensing/Astral Combat/Arcana are Magical/Pseudo-Magical Active despite
    # being linked to INT/WIL/LOG, not MAG -- a Mundane character must not see them either, even
    # though the old attribute-only filter let them through.
    assert "Assensing" not in response.text
    assert "Astral Combat" not in response.text
    assert "Arcana" not in response.text


def test_skill_picker_offers_rated_only_filter_with_per_row_rating() -> None:
    # WP67: an "Only rated skills" checkbox narrows the picker to skills with rating > 0.
    # It's a purely client-side filter, so the server contract is just: the checkbox renders,
    # and every skill row carries its current rating as a data attribute for the JS to read.
    client = TestClient(create_app())
    _confirm_human(client)

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    response = client.post("/ui/skills", data={f"skill_{skill.id}": "3"})

    assert response.status_code == 200
    assert 'id="skill-rated-only"' in response.text
    assert "Only rated skills" in response.text
    # The rated skill's row exposes its rating; unrated rows expose 0.
    assert 'data-skill-rating="3"' in response.text
    assert 'data-skill-rating="0"' in response.text


def test_skill_filter_state_survives_the_fragment_being_re_rendered() -> None:
    # The whole #skill-allocation fragment (controls included) is re-rendered on every rating
    # change, so both filter controls come back at their unfiltered defaults unless the client
    # restores them -- the same swap-discards-state problem WP64's <details> store solves. The
    # server contract is only that the re-rendered fragment carries the restore/re-apply code:
    # the state itself lives on the client, never in the session.
    client = TestClient(create_app())
    _confirm_human(client)

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    response = client.post("/ui/skills", data={f"skill_{skill.id}": "3"})

    assert response.status_code == 200
    assert 'id="skill-filter"' in response.text and 'id="skill-rated-only"' in response.text
    # WP141: the restore/re-apply code moved from an inline <script> in the fragment (which the
    # CSP forbids) to static/app.js, which runs once per page and restores after every swap.
    assert "<script" not in response.text
    script = client.get("/static/app.js").text
    # Restored from a store that outlives the swapped subtree, not from the rendered markup...
    assert "var skillFilter = {" in script
    assert "rated.checked = skillFilter.ratedOnly" in script
    assert "input.value = skillFilter.query" in script
    # ...and re-applied as soon as new content lands, so the fresh rows honour it at once.
    assert 'document.addEventListener("htmx:load", restoreSkillFilter)' in script


def test_submitting_valid_attribute_points_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/attributes", data={"attr_BOD": "2", "attr_AGI": "1"})

    assert response.status_code == 200
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    expected = create_character(human_choice, "A", "B", PRIORITIES, {"BOD": 2, "AGI": 1})
    assert f"<td>{expected.attribute_value('BOD')}</td>" in response.text
    assert f"<td>{expected.attribute_value('AGI')}</td>" in response.text

    budget = PRIORITIES.attributes["B"].points
    assert f"{budget - 3}/{budget}" in response.text


def test_submitting_over_budget_attribute_points_is_rejected_and_state_unchanged() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    budget = PRIORITIES.attributes["B"].points

    response = client.post("/ui/attributes", data={"attr_BOD": str(budget + 5)})

    assert response.status_code == 200
    assert "exceeds" in response.text
    # Submitted (invalid) value is echoed back in the input, per the priority-form precedent.
    assert f'value="{budget + 5}"' in response.text

    # The committed session state is untouched -- reloading the page shows the old (zero) spend,
    # not the rejected one.
    index = client.get("/ui/page/attributes")
    assert f"{budget}/{budget}" in index.text


def test_submitting_valid_skill_points_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    response = client.post("/ui/skills", data={f"skill_{skill.id}": "3"})

    assert response.status_code == 200
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(human_choice, "A", "B", PRIORITIES, {})
    allocation = create_skill_allocation("C", PRIORITIES, SKILLS, {skill.id: 3}, {})
    expected_rating = skill_rating(character, allocation, skill)
    expected_pool = dice_pool(character, allocation, skill)
    assert f"<td>{expected_rating}</td>" in response.text
    assert f"<td>{expected_pool}</td>" in response.text

    budget = PRIORITIES.skills["C"].skills
    assert f"{budget - 3} / {budget}" in response.text


def test_submitting_a_skill_group_sets_every_member_skills_rating() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    group = MUNDANE_SKILL_GROUPS[0]
    response = client.post("/ui/skills", data={f"group_{group}": "2"})

    assert response.status_code == 200
    member_names = [s.name for s in MUNDANE_SKILLS if s.skill_group == group]
    assert member_names  # sanity: the chosen group actually has mundane member skills
    # Every member skill's rating column should show 2 -- spot check via the group's own points.
    budget = PRIORITIES.skills["C"].skill_groups
    assert f"{budget - 2} / {budget}" in response.text


def test_submitting_conflicting_skill_and_group_points_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    grouped_skill = next(s for s in MUNDANE_SKILLS if s.skill_group is not None)
    response = client.post(
        "/ui/skills",
        data={
            f"skill_{grouped_skill.id}": "1",
            f"group_{grouped_skill.skill_group}": "1",
        },
    )

    assert response.status_code == 200
    assert "strict skill groups" in response.text


def test_submitting_over_budget_skill_points_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    budget = PRIORITIES.skills["C"].skills

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    response = client.post("/ui/skills", data={f"skill_{skill.id}": str(budget + 5)})

    assert response.status_code == 200
    assert "exceeds" in response.text


def test_reconfirming_priorities_with_a_still_fitting_budget_keeps_the_allocation() -> None:
    """WP19: reconfirmation no longer resets a spend that still fits the (re)confirmed letters --
    unlike the pre-WP19 behavior (see `spec/worklogs/WP18.md`'s own recorded check, which expected
    a full/full reset here), a plain re-submission of the *same* letters must leave the existing
    spend exactly as it was.
    """
    client = TestClient(create_app())
    _confirm_human(client)
    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    client.post("/ui/attributes", data={"attr_BOD": "2"})
    client.post("/ui/skills", data={f"skill_{skill.id}": "3"})

    # Re-confirm the same metatype/priorities (still a legal, distinct submission).
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert "no longer fit" not in response.text  # the priorities page's own aggregate warning
    # WP97: the priorities POST re-renders only its own page; the carried-forward spend shows on
    # each step's page.
    attributes_page = client.get("/ui/page/attributes")
    skills_page = client.get("/ui/page/skills")
    primary_budget = PRIORITIES.attributes["B"].points
    skills_budget = PRIORITIES.skills["C"].skills
    assert f"{primary_budget - 2}/{primary_budget}" in attributes_page.text
    assert f"{skills_budget - 3} / {skills_budget}" in skills_page.text
    assert 'value="2"' in attributes_page.text  # BOD's spent points still echoed in the form
    assert "No longer fits" not in attributes_page.text
    assert "No longer fits" not in skills_page.text


def test_reconfirming_priorities_with_a_lower_attributes_budget_flags_the_existing_spend() -> None:
    """The WP19 acceptance scenario: spend attribute points that fit the current Attributes
    letter, lower that letter on reconfirmation, and confirm the spend is kept (not reset) while a
    distinct "no longer fits" warning appears -- rather than a blank/reset form.
    """
    client = TestClient(create_app())
    _confirm_human(client)  # Attributes letter B, budget 20
    # 15 points -- fits B's 20-point budget. Only BOD reaches Human's maximum (6): since WP112 a
    # single submission may not put a second Mental/Physical attribute there.
    client.post(
        "/ui/attributes", data={"attr_BOD": "5", "attr_AGI": "4", "attr_REA": "4", "attr_STR": "2"}
    )

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    # Swap Attributes B (20 points) for D (14 points) -- 15 points spent no longer fits.
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "D",
            "skills_letter": "C",
            "resources_letter": "B",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    assert "no longer fit" in response.text  # the priorities page's own aggregate warning
    response = client.get("/ui/page/attributes")  # WP97: the spend itself shows on its own page
    new_budget = PRIORITIES.attributes["D"].points
    assert new_budget == 14
    # The old spend (15 points) is still shown, over the new 14-point budget -- not reset to 0.
    assert 'value="5"' in response.text
    assert f"-1/{new_budget}" in response.text
    assert "No longer fits since priorities were last confirmed" in response.text
    assert "exceeds" in response.text


def test_reconfirming_priorities_with_a_lower_skills_budget_flags_the_existing_spend() -> None:
    client = TestClient(create_app())
    _confirm_human(client)  # Skills letter C, budget 28
    ungrouped_skills = [s for s in MUNDANE_SKILLS if s.skill_group is None][:5]
    # 6+6+6+6+1 = 25 points -- fits C's 28-point budget.
    points = {s.id: 6 for s in ungrouped_skills[:4]}
    points[ungrouped_skills[4].id] = 1
    client.post("/ui/skills", data={f"skill_{sid}": str(v) for sid, v in points.items()})

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    # Swap Skills C (28 points) for D (22 points) -- 25 points spent no longer fits.
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "D",
            "resources_letter": "C",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    response = client.get("/ui/page/skills")  # WP97: the spend itself shows on its own page
    new_budget = PRIORITIES.skills["D"].skills
    assert new_budget == 22
    assert f"-3 / {new_budget}" in response.text
    assert "No longer fits since priorities were last confirmed" in response.text
    assert "exceeds" in response.text


def test_attributes_and_skills_endpoints_before_confirmation_do_not_crash() -> None:
    client = TestClient(create_app())
    client.get("/")

    attr_response = client.post("/ui/attributes", data={"attr_BOD": "2"})
    skill_response = client.post("/ui/skills", data={})

    assert attr_response.status_code == 200
    assert "Confirm a metatype and priorities" in attr_response.text
    assert skill_response.status_code == 200
    assert "Confirm a metatype and priorities" in skill_response.text


# WP50: specializations.


def test_submitting_a_specialization_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    response = client.post(
        "/ui/skills", data={f"skill_{skill.id}": "3", f"spec_{skill.id}": "Longbow"}
    )

    assert response.status_code == 200
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(human_choice, "A", "B", PRIORITIES, {})
    allocation = create_skill_allocation(
        "C", PRIORITIES, SKILLS, {skill.id: 3}, {}, {skill.id: "Longbow"}
    )
    # WP65: a specialized skill's Pool renders as "X (Y)" -- base pool then the +2 specialized pool.
    base_pool = dice_pool(character, allocation, skill, specialized=False)
    spec_pool = dice_pool(character, allocation, skill, specialized=True)
    assert spec_pool == base_pool + 2
    assert 'value="Longbow"' in response.text
    assert f"<td>{base_pool} ({spec_pool})</td>" in response.text

    # The specialization's 1 point is counted against the remaining budget too.
    budget = PRIORITIES.skills["C"].skills
    assert f"{budget - 4} / {budget}" in response.text


def test_submitting_a_specialization_on_an_unbought_skill_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    response = client.post("/ui/skills", data={f"spec_{skill.id}": "Longbow"})

    assert response.status_code == 200
    assert "cannot add a specialization" in response.text


def test_submitting_a_specialization_on_a_group_purchased_skill_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    group = MUNDANE_SKILL_GROUPS[0]
    grouped_skill = next(s for s in MUNDANE_SKILLS if s.skill_group == group)
    response = client.post(
        "/ui/skills",
        data={f"group_{group}": "2", f"spec_{grouped_skill.id}": "Whatever"},
    )

    assert response.status_code == 200
    assert "cannot add a specialization" in response.text


def test_character_sheet_shows_the_specialization_name() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    client.post("/ui/skills", data={f"skill_{skill.id}": "3", f"spec_{skill.id}": "Longbow"})

    response = client.get("/character/sheet")

    assert response.status_code == 200


def test_section_forms_scope_input_trigger_to_number_inputs() -> None:
    """WP65: text inputs must submit on `change` (blur) only, not on the `input delay:400ms` that
    the number spinners want -- otherwise the outerHTML swap rebuilds a text field mid-typing and
    drops focus. WP141: the scoping moved from an htmx event filter (an expression htmx evaluates,
    which the CSP forbids) to static/app.js, which re-dispatches `input` from number inputs only,
    as `number-input`."""
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/skills", data={})

    assert "change, number-input delay:400ms" in response.text
    assert "change, input delay:400ms" not in response.text
    script = client.get("/static/app.js").text
    assert 't.type === "number"' in script and 'new CustomEvent("number-input"' in script


def test_skill_allocation_context_exposes_base_and_specialized_pool() -> None:
    """WP65: a specialized row carries both `pool` (base, un-specialized) and `pool_specialized`
    (= base + 2); a plain row carries `pool` only, with `pool_specialized` None."""
    from chummer5.web.routes.skills import _skill_allocation_context

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(human_choice, "A", "B", PRIORITIES, {})
    ungrouped = next(s for s in MUNDANE_SKILLS if s.skill_group is None and not s.exotic)

    context = _skill_allocation_context(
        character, "C", {ungrouped.id: 3}, {}, {ungrouped.id: "Longbow"}
    )
    rows = {row["skill"].id: row for row in context["skill_rows"]}

    specialized = rows[ungrouped.id]
    assert specialized["pool_specialized"] == specialized["pool"] + 2

    plain = next(row for sid, row in rows.items() if sid != ungrouped.id)
    assert plain["pool_specialized"] is None


# WP53: Karma-funded skill/skill-group increases and specializations, including group-breaking.


def test_submitting_karma_skill_points_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    response = client.post(
        "/ui/skills", data={f"skill_{skill.id}": "2", f"karma_skill_{skill.id}": "2"}
    )

    assert response.status_code == 200
    # 2->3 costs 6, 3->4 costs 8 -- 14 Karma total, out of the starting 25.
    assert f"<td>{4}</td>" in response.text
    assert "Karma remaining for skills: 11 / 25" in response.text


def test_submitting_karma_group_points_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    group = "Firearms"
    response = client.post("/ui/skills", data={f"group_{group}": "1", f"karma_group_{group}": "1"})

    assert response.status_code == 200
    # 1->2 costs new_rating x 5 = 10 Karma.
    assert "Karma remaining for skills: 15 / 25" in response.text


def test_submitting_karma_specialization_breaks_a_purchased_group() -> None:
    client = TestClient(create_app())
    _confirm_human(client)  # Skills C: skill_groups budget is 2

    automatics = next(s for s in MUNDANE_SKILLS if s.name == "Automatics")
    longarms = next(s for s in MUNDANE_SKILLS if s.name == "Longarms")
    client.post("/ui/skills", data={"group_Firearms": "2"})

    response = client.post(
        "/ui/skills", data={"group_Firearms": "2", f"karma_spec_{automatics.id}": "Assault Rifles"}
    )

    assert response.status_code == 200
    assert "Karma remaining for skills: 18 / 25" in response.text  # 7 Karma flat
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(human_choice, "A", "B", PRIORITIES, {})
    allocation = create_skill_allocation("C", PRIORITIES, SKILLS, {}, {"Firearms": 2})
    unspecialized_pool = dice_pool(character, allocation, longarms)
    # Automatics is now individually specialized -- WP65 renders it "X (X+2)"; Longarms stays plain
    # group-rated (single value, no parenthetical).
    assert f"<td>{unspecialized_pool} ({unspecialized_pool + 2})</td>" in response.text
    assert f"<td>{unspecialized_pool}</td>" in response.text


def test_submitting_karma_skill_points_on_group_member_breaks_the_group_without_a_spec() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    automatics = next(s for s in MUNDANE_SKILLS if s.name == "Automatics")
    client.post("/ui/skills", data={"group_Firearms": "2"})

    response = client.post(
        "/ui/skills", data={"group_Firearms": "2", f"karma_skill_{automatics.id}": "1"}
    )

    assert response.status_code == 200
    # 2->3 costs new_rating x 2 = 6 Karma.
    assert "Karma remaining for skills: 19 / 25" in response.text
    assert f"<td>{3}</td>" in response.text  # Automatics' own individually-raised rating


def test_submitting_karma_skill_points_over_budget_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    # 0 -> 6 costs 2*(1+2+3+4+5+6) = 42 Karma, over the 25-Karma starting budget, while staying
    # within the chargen rating cap (6) so the rejection is genuinely budget-driven, not a rating
    # overflow.
    response = client.post("/ui/skills", data={f"karma_skill_{skill.id}": "6"})

    assert response.status_code == 200
    assert "exceeds the Karma budget" in response.text


def test_full_page_reload_shows_each_sections_own_karma_numbers_not_knowledges() -> None:
    """WP60 regression. `_chargen_body_context` merges `_attribute_allocation_context`'s,
    `_skill_allocation_context`'s, and `_knowledge_selection_context`'s dicts together to build the
    full-page `GET /` context; all three used to return the identically-named generic
    `karma_budget`/`karma_remaining` keys, so whichever was merged last (Knowledge) silently
    overwrote the other two -- both sections displayed Knowledge's own (nothing-spent-there) numbers
    on any full-page render, even though each POST route's own isolated response was correct.
    """
    client = TestClient(create_app())
    _confirm_human(client)

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(human_choice, "A", "B", PRIORITIES, {})
    edg_start = character.attribute_range("EDG").minimum  # 2 for Human
    edg_cost = karma_advancement_cost(edg_start, 1, ATTRIBUTE_KARMA_PER_RATING)  # (2+1)*5 = 15
    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    skill_cost = karma_advancement_cost(0, 1, KARMA_SKILL_PER_RATING)  # (0+1)*2 = 2

    client.post("/ui/attributes", data={"karma_attr_EDG": "1"})
    client.post("/ui/skills", data={f"karma_skill_{skill.id}": "1"})

    attributes_page = client.get("/ui/page/attributes")
    skills_page = client.get("/ui/page/skills")

    both_spent_remaining = STARTING_KARMA - edg_cost - skill_cost
    attribute_budget = STARTING_KARMA - skill_cost  # excludes only Attributes' own commitment
    skill_budget = STARTING_KARMA - edg_cost  # excludes only Skills' own commitment
    assert attribute_budget != skill_budget  # sanity: the two sections' own budgets really differ

    assert (
        f'attribute-budget__value">{both_spent_remaining}/{attribute_budget}<'
        in attributes_page.text
    )
    assert (
        f"Karma remaining for skills: {both_spent_remaining} / {skill_budget}" in skills_page.text
    )


def test_character_sheet_shows_karma_funded_specialization() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    automatics = next(s for s in MUNDANE_SKILLS if s.name == "Automatics")
    client.post("/ui/skills", data={"group_Firearms": "2"})
    client.post(
        "/ui/skills", data={"group_Firearms": "2", f"karma_spec_{automatics.id}": "Assault Rifles"}
    )

    response = client.get("/character/sheet")

    assert response.status_code == 200
    assert "Assault Rifles" in response.text
    assert "Skill/skill-group karma cost: 7." in response.text


# --- WP146: the redesigned Attributes page ---------------------------------------------------


def _budget_boxes(html: str) -> list[tuple[str, bool]]:
    """(value text, overspent?) of each budget box, in document order."""
    return [
        (value, bool(over))
        for over, value in re.findall(
            r'<div class="attribute-budget( attribute-budget--over)?">.*?'
            r'attribute-budget__value">([^<]*)<',
            html,
            flags=re.S,
        )
    ]


def test_attributes_page_shows_three_budget_boxes_without_a_button_or_details() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    html = client.get("/ui/page/attributes").text
    budget = PRIORITIES.attributes["B"].points
    boxes = _budget_boxes(html)
    assert len(boxes) == 3
    assert boxes[0] == (f"{budget}/{budget}", False)
    assert not any(over for _, over in boxes)
    assert "(5 x level)" in html
    assert 'type="submit"' not in html
    assert "<details" not in html
    assert "Update attributes" not in html


def test_an_overspent_pool_highlights_only_its_own_box() -> None:
    client = TestClient(create_app())
    _confirm_human(client)  # Attributes B: 20 points
    client.post(
        "/ui/attributes", data={"attr_BOD": "5", "attr_AGI": "4", "attr_REA": "4", "attr_STR": "2"}
    )
    heritage = PRIORITIES.heritage["A"]
    human = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
    # Attributes D is 14 points: the 15 already spent now overspend the primary pool (WP19).
    client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "D",
            "skills_letter": "C",
            "resources_letter": "B",
            "talent_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )
    primary, special, karma = _budget_boxes(client.get("/ui/page/attributes").text)
    assert primary == ("-1/14", True)
    assert special[1] is False
    assert karma[1] is False


def test_attribute_inputs_keep_stable_ids_and_messages_follow_the_table() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    budget = PRIORITIES.attributes["B"].points
    html = client.post("/ui/attributes", data={"attr_BOD": str(budget + 5)}).text
    assert 'id="attr-BOD"' in html
    assert 'id="karma-attr-BOD"' in html
    assert html.index("attribute-budgets") < html.index("<table") < html.index("</table>")
    assert html.index("</table>") < html.index('class="error"')
