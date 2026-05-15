---
name: mobile-ui-verification
description: Verify local mobile web UI, especially phone-like landscape layouts and touch interactions, with system Chrome plus bundled Playwright when the Codex in-app Browser cannot set viewport, touch, or coarse pointer emulation. Use for NTE Board Game mobile table checks, screenshots, responsive layout regressions, map marker sizing, touch-first previews, and other localhost mobile verification tasks.
---

# Mobile UI Verification

Use this skill when a local page must be verified as a phone-like mobile browser and the in-app Browser cannot emulate viewport or touch accurately.

## Preferred Flow

1. Confirm the local service is reachable, usually `http://127.0.0.1:5001` for this repo.
2. Prefer the Codex Browser plugin if it can set the requested viewport and touch/coarse-pointer behavior.
3. If the Browser plugin is unavailable or cannot emulate mobile conditions, use the bundled Node runtime with Playwright and system Chrome.
4. For NTE table verification, run `scripts/verify-nte-mobile-table.mjs` from this skill.
5. Inspect both the screenshot and the printed metrics. Metrics are the guardrail; screenshots catch the visual feel.

## Why This Fallback Exists

The in-app Browser can screenshot localhost pages, but in some sessions its Node REPL bridge or viewport capability may be unavailable. The fallback uses:

- Bundled Node from `load_workspace_dependencies`.
- Bundled `playwright` package.
- System Chrome at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.
- `context.addInitScript()` to force `matchMedia('(pointer: coarse)')` and `matchMedia('(hover: none)')` when Playwright's `hasTouch` does not affect CSS media queries.

If connecting to localhost fails with sandbox `EPERM`, rerun the command with escalation and a short justification that it needs to connect to the local dev server.

## NTE Table Script

Script path:

```text
.agents/skills/mobile-ui-verification/scripts/verify-nte-mobile-table.mjs
```

Typical command:

```bash
/Users/bytedance/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node .agents/skills/mobile-ui-verification/scripts/verify-nte-mobile-table.mjs
```

Useful environment overrides:

```bash
BASE_URL=http://127.0.0.1:5001 WIDTH=1024 HEIGHT=461 DPR=2 MAP_ZOOM=max \
/Users/bytedance/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node .agents/skills/mobile-ui-verification/scripts/verify-nte-mobile-table.mjs
```

The script:

- Logs in with mock account `10001 / 654321` unless overridden.
- Creates or resumes a game state if possible.
- Rolls dice if the game is still in dice phase.
- Opens `/table` in a mobile landscape viewport.
- Forces coarse pointer/hover-none media queries by default.
- Sets the map zoom slider, taps a reachable map cell once to trigger touch preview, screenshots the page, and prints marker metrics.

Key overrides:

```text
PLAYER_UID=10001
LOGIN_CODE=654321
BASE_URL=http://127.0.0.1:5001
WIDTH=1024
HEIGHT=461
DPR=2
MAP_ZOOM=max
FORCE_COARSE=1
SCREENSHOT_PATH=/private/tmp/nte_mobile_table_verify.png
CHROME_EXECUTABLE=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

## Reading Results

Check these printed metrics first:

- `pointerCoarse` should be `true` for touch-preview testing.
- `mapZoom` should match the requested zoom.
- `.token-player`, `.player-chip`, `.preview-dot`, and `.preview-line` sizes should remain stable at high map zoom.
- `previewDots` should be present after the first tap. If absent, the tap may have moved instead of previewed.

Then view the screenshot with `view_image` or attach it in the final answer:

```text
/private/tmp/nte_mobile_table_verify.png
```

## Cautions

- This workflow can mutate the local mock account's game state by rolling dice or triggering one preview tap. It should not perform the second tap that confirms movement unless the task explicitly asks for it.
- Do not use this as a replacement for broader desktop browser testing. Use it specifically for phone-like layout and touch behavior.
- If Playwright's bundled Chromium is missing, do not download browsers unless the user approves network access; use system Chrome instead.
