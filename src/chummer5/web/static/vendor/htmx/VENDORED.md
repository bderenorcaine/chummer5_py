# Vendored: htmx

- **Version:** 2.0.10
- **File:** `htmx.min.js`, fetched from `https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js`
- **License:** Zero-Clause BSD (`LICENSE`, fetched from the same package) — permissive, no
  attribution burden, compatible with this project's GPLv3.

Vendored (not CDN-loaded) per `Project Overview.md`'s stack decision: the app must run fully
offline/local-first. To update, re-fetch both files from
`https://unpkg.com/htmx.org@<version>/dist/htmx.min.js` and `.../LICENSE`, and bump the version
here and in `templates/base.html`'s script tag comment.
