---
name: mobile-ui-verification
description: Verify local mobile web UI, especially phone-like landscape layouts and touch interactions, with bundled Playwright/Chromium when the Codex in-app Browser cannot set viewport, touch, or coarse pointer emulation. Use for NTE Board Game mobile table checks, screenshots, responsive layout regressions, map marker sizing, touch-first previews, and other localhost mobile verification tasks.
---

# Mobile UI Verification

Use this skill when a local page must be verified as a phone-like mobile browser and the in-app Browser cannot emulate viewport or touch accurately.

## Preferred Flow

1. Confirm the local service is reachable, usually `http://127.0.0.1:5001` for this repo.
2. Prefer the Codex Browser plugin if it can set the requested viewport and touch/coarse-pointer behavior.
3. If the Browser plugin is unavailable or cannot emulate mobile conditions, use the bundled Node runtime with Playwright/Chromium. Set `CHROME_EXECUTABLE` only when a specific local browser is needed.
4. For NTE duel mobile verification, run `scripts/verify-nte-mobile-table.mjs` from this skill.
5. Inspect both the screenshots and the printed metrics. Metrics are the guardrail; screenshots catch the visual feel.

## Why This Fallback Exists

The in-app Browser can screenshot localhost pages, but in some sessions its Node REPL bridge or viewport capability may be unavailable. The fallback uses:

- Bundled Node from `load_workspace_dependencies`.
- Bundled `playwright` package.
- Playwright's configured Chromium by default, or `CHROME_EXECUTABLE` when explicitly provided.
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
BASE_URL=http://127.0.0.1:5001 WIDTH=944 HEIGHT=427 DPR=3 \
/Users/bytedance/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node .agents/skills/mobile-ui-verification/scripts/verify-nte-mobile-table.mjs
```

The script:

- Logs in with mock account `10001 / 654321` unless overridden.
- Starts a fresh `trial` run by default so table screenshots are not polluted by whichever scenario the mock account last had open.
- Rolls dice if the game is still in dice phase.
- Opens `/table` in a mobile landscape viewport.
- Forces coarse pointer/hover-none media queries by default.
- Defaults to the current hard mobile acceptance viewport `944 x 427 @ DPR 3`, matching a `2832 x 1281` device screenshot.
- Renders temporary local verification cards on both player and opponent battlefields before measuring; this is only a DOM/UI check and does not write backend state.
- Set `REAL_PLAY_CARD=1` only when explicitly checking the real local planning draft flow before the synthetic layout measurement.
- Verifies every visible hand card keeps a readable card name and both battlefield cards are fully inside their battlefield rows.
- Verifies visible hand cards have bottom clearance from the viewport so their lower border is not clipped on phone browsers.
- Verifies the mobile battlefield rule panel is pinned to the whole viewport's lower-left corner and does not overlap the player discard/deck controls.
- Verifies the player battlefield card is wide enough for readable visible stat badges and those badges do not overlap.
- Verifies the middle battlefield area is only a single fixed line, with no embedded score rows.
- Verifies the mobile score readout stays beside the end-turn button, uses the old frameless power-number style, and highlights the initiative side.
- Verifies the mobile score readout is arranged in three vertical lines: opponent on top, status in the middle, player on the bottom.
- Verifies the mobile score readout center and the end-turn button center are horizontally aligned with the battlefield midline.
- Verifies the player/opponent battlefield rows are equal height and the fixed midline is slightly above the older mobile baseline.
- Verifies battlefield containers allow visible overflow so reveal/flip animations are not clipped by hard row bounds.
- Verifies the normal battlefield card distance to the fixed midline remains stable and symmetric.
- Verifies battlefield card attribute/category chips are balanced: the attribute chip is icon-only and narrow, while the category chip keeps enough width without clipping the icon.
- Verifies the contest bar is centered on a fixed battlefield midline and that the midline does not move when both battlefield rows are empty.
- Verifies opponent/player deck and discard zones use matching sizes.
- Opens a synthetic table selection overlay, screenshots it, verifies choice cards use the same readable name treatment as hand cards, and verifies source labels are hidden when every option comes from deck/graveyard.
- Opens and screenshots table tutorial, build page, build long-press previews, and build tutorial under the same viewport.
- Verifies build-page long press: catalog cards open a right-docked preview, deck/build-set cards open a left-docked preview, and both previews show concrete effect text.

Key overrides:

```text
PLAYER_UID=10001
LOGIN_CODE=654321
BASE_URL=http://127.0.0.1:5001
WIDTH=944
HEIGHT=427
DPR=3
FORCE_COARSE=1
PLAY_CARD=1
FORCE_NEW_RUN=1
SCENARIO=trial
SCREENSHOT_DIR=/private/tmp
CHROME_EXECUTABLE=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
REAL_PLAY_CARD=0
```

## Reading Results

Check these printed metrics first:

- `pointerCoarse` and `hoverNone` should be `true`.
- `results.table.pass` should be `true`.
- `results.table.overlaps.firstPlayerCardVsHandDock.area` should be `0`.
- `results.table.overlaps.firstPlayerCardVsAnyHandCard` should be `null` or area `0`.
- `results.table.handTitlesVisible` should be `true`.
- `results.table.handCardsInsideViewportBottom` should be `true`.
- `results.table.mobileScoreFramelessBesideEndTurn` should be `true`.
- `results.table.mobileScoreThreeLineOrder` should be `true`.
- `results.table.rightControlsAlignedToMidline` should be `true`.
- `results.table.middleAreaOnlyLine` should be `true`.
- `results.table.equalBattlefieldRows` should be `true`.
- `results.table.boardCardChipsBalanced` should be `true`.
- `results.table.ruleLineBottomLeft` should be `true`.
- `results.table.playerCardStatsReadable` should be `true`.
- `results.table.playerCardFullyInsideSlots` should be `true`.
- `results.table.opponentCardFullyInsideSlots` should be `true`.
- `results.table.battlefieldOverflowVisible` should be `true`.
- `results.table.cardDistanceToMidlineStable` should be `true`.
- `results.table.contestCenteredOnFixedMidline` should be `true`.
- `results.table.midlineStableWithoutCards` should be `true`.
- `results.table.deckZoneSizesMatch` should be `true`.
- `results.table.selection.pass` should be `true`.
- `results.table.selection.sourceBadgesHidden` should be `true`.
- `results.table.selection.cardTitlesVisible` should be `true`.
- `results.build.previews.catalog.rightDocked` should be `true`.
- `results.build.previews.deck.leftDocked` should be `true`.
- `results.build.previews.catalog.metrics.effectTextLength` and `results.build.previews.deck.metrics.effectTextLength` should be greater than `0`.
- `results.tableTutorial.pass`, `results.build.pass`, and `results.buildTutorial.pass` should all be `true`.

Then view the screenshot with `view_image` or attach it in the final answer:

```text
/private/tmp/nte_mobile_duel_table_944x427_dpr3.png
/private/tmp/nte_mobile_table_selection_944x427_dpr3.png
/private/tmp/nte_mobile_table_tutorial_944x427_dpr3.png
/private/tmp/nte_mobile_build_944x427_dpr3.png
/private/tmp/nte_mobile_build_catalog_preview_944x427_dpr3.png
/private/tmp/nte_mobile_build_deck_preview_944x427_dpr3.png
/private/tmp/nte_mobile_build_tutorial_944x427_dpr3.png
```

## Cautions

- This workflow can mutate the local mock account's game state by starting a fresh trial run by default and rolling dice. Set `FORCE_NEW_RUN=0` to verify the existing run instead. The played hand card is only a client-side planning draft unless the script is changed to end the turn.
- Do not use this as a replacement for broader desktop browser testing. Use it specifically for phone-like layout and touch behavior.
- If Playwright's bundled Chromium is missing, do not download browsers unless the user approves network access; use system Chrome instead.
