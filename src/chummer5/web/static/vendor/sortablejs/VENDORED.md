# Vendored: SortableJS

- **Version:** 1.15.7
- **File:** `Sortable.min.js`, from the npm package `sortablejs@1.15.7`
  (`https://registry.npmjs.org/sortablejs/-/sortablejs-1.15.7.tgz`, tarball SHA-1
  `83a0bddc472117ee328dea20b2e6f490fed20f86` as published by the registry). The same file is
  served at `https://unpkg.com/sortablejs@1.15.7/Sortable.min.js`.
- **SHA-256 of `Sortable.min.js`:** `bf4241bc73fef7f11c59a283a69fe8051cdd31c6d8ff5a2b9ba219e7831fcf76`
- **License:** MIT (`LICENSE`, from the same package). It is compatible with this project's
  GPLv3, and the license text must ship with it. The repository's `NOTICE` lists it too.
- **Approved:** by the user on 2026-10-05, for the Priorities page's drag-to-reorder (Phase Z,
  WP144; see `spec/decisions-log.md`).

Vendored, not loaded from a CDN, for the same reasons as htmx: the app runs offline, and the
Content-Security-Policy allows scripts from `'self'` only. The library uses no `eval` or
`new Function`. Its only style write is through the CSSOM, which `style-src 'self'` doesn't
govern.

To update, fetch the new tarball from the npm registry and check its `dist.shasum`. Copy
`package/Sortable.min.js` and `package/LICENSE` here, then bump the version and checksums in
this file and the version in `templates/base.html`'s script comment.
