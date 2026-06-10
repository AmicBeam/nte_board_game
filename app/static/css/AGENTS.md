# CSS Module Guidelines

- `app.css` is the stylesheet entrypoint only. Keep it as an ordered list of `@import` statements and do not add page rules there.
- Put new CSS in `modules/` by ownership:
  - `foundation.css`: tokens, reset, shared cards, buttons, forms, and global shell layout.
  - `catalog-cards.css`: reusable character, build, and item card primitives.
  - `build-page.css`, `codex-page.css`: page-specific layout and states.
  - `table-*.css`: table page layout, map, sidebar, overlays, and table-specific states.
  - `responsive.css`: media queries and viewport-specific overrides.
- Preserve import order when moving rules. Later modules may intentionally override earlier shared primitives.
- Keep high-frequency map interactions cheap: prefer transforms, CSS variables, stable dimensions, and lightweight overlays over expensive shadows or layout-triggering changes.
- Do not encode game rules in CSS. CSS should only express presentation and interaction state returned by the backend or table UI code.
