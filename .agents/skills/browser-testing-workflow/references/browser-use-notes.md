# Browser Use Notes

Use Node REPL with the Browser plugin. Good operations include `tab.goto`, `tab.playwright.domSnapshot`, locator clicks/fills, screenshots, and reloads.

Avoid broad page evaluation for inspection. Prefer DOM snapshots, locators, screenshots, and observable UI state.

After significant frontend edits, reload the page and re-run the relevant path. For CSS/icon issues, compare screenshots at the target viewport and inspect image load failures in console output when available.

When testing login-gated local apps, prefer the same UI flow users use unless the user explicitly asks for API seeding or shortcut setup.
