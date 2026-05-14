---
name: browser-testing-workflow
description: Use the Codex in-app Browser/browser-use plugin through the Node REPL to test local web apps, localhost pages, UI flows, screenshots, DOM state, console errors, responsive layouts, and visual regressions after frontend changes. Use when Codex needs to open, inspect, click, type, reload, screenshot, or verify a browser-rendered local target.
---

# Browser Testing Workflow

## Quick Start

Prefer the Browser plugin for local UI verification. Do not use macOS `open` as a substitute when the user asks for browser testing or when a frontend change needs visual verification.

Bootstrap the in-app browser from the Node REPL:

```js
if (!globalThis.agent) {
  const { setupAtlasRuntime } = await import('/Users/bytedance/.codex/plugins/cache/openai-bundled/browser-use/0.1.0-alpha2/scripts/browser-client.mjs');
  await setupAtlasRuntime({ globals: globalThis });
}
if (!globalThis.browser) globalThis.browser = await agent.browsers.get('iab');
await browser.nameSession('local UI test');
if (typeof tab === 'undefined') globalThis.tab = await browser.tabs.new();
```

Then navigate with `await tab.goto('http://127.0.0.1:PORT/...')` and inspect with `await tab.playwright.domSnapshot()`.

## Testing Loop

1. Start or confirm the local dev server with the project’s normal command. If a known server is already running, reuse it.
2. Navigate to the exact route under test and wait for the app to settle.
3. Use a DOM snapshot first: identify controls, labels, data attributes, and major rendered regions before clicking.
4. Interact like a user: click visible controls, type into real inputs, and reload after code changes.
5. Capture screenshots for layout-sensitive checks, especially maps, canvas/3D, responsive pages, or icon rendering.
6. Check browser console output when available; report user-visible errors and failed asset loads.
7. For ambiguous selectors, count matches or narrow by role/text before clicking.
8. After navigation or mutation, take a fresh snapshot instead of relying on stale handles.

## Local App Checks

For game boards and map UIs, verify both data and pixels:

- Map dimensions match backend payload.
- Icons stay inside their cells and do not overflow the grid.
- Hover/click previews update without console errors.
- Asset paths resolve, including SVG and static image resources.
- Text does not overlap controls at desktop and mobile widths.

Read `references/browser-use-notes.md` for guardrails and useful snippets.
