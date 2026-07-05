# Static Module Guidelines

- `common/css/app.css` is the stylesheet entrypoint only. Keep it as an ordered list of `@import` statements and do not add page rules there.
- Put shared CSS in `common/css/`:
  - `foundation.css`: tokens, reset, shared cards, buttons, forms, and global shell layout.
  - `catalog-cards.css`: reusable character, build, and item card primitives.
  - `responsive.css`: shared media queries and viewport-specific overrides.
- Put card game page CSS in `card_game/css/`:
  - `build-page.css`, `codex-page.css`, `analytics-page.css`: page-specific layout and states.
  - `duel-table*.css`: table page layout, board, sidebar, overlays, and table-specific states.
- Put Kongmu page CSS in `kongmu/css/`.
- Put shared JavaScript in `common/js/`; page-owned JavaScript belongs to its module, such as `card_game/js/` or `kongmu/js/`.
- Preserve import order when moving rules. Later modules may intentionally override earlier shared primitives.
- Keep high-frequency map interactions cheap: prefer transforms, CSS variables, stable dimensions, and lightweight overlays over expensive shadows or layout-triggering changes.
- Do not encode game rules in CSS. CSS should only express presentation and interaction state returned by the backend or table UI code.
