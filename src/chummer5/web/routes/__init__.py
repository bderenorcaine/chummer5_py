"""Per-chargen-step `APIRouter` modules (WP62) -- see `spec/plan/phase-r-architecture-cleanup.md`.

Each module owns one chargen step's `_parse_*` form helpers, `_relink_*`/`_replace_committed_*`
Improvement-carry-forward helpers, its own `_*_context` builder, and its `@router.get`/`@router
.post("/ui/...")` route(s). `chummer5.web.app.create_app()` mounts every module's `router` onto the
`FastAPI` app; URL paths are unchanged from before this split.
"""
