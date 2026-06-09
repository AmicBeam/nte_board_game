# Iteration 03 - Extreme-Case Convergence

Date: 2026-06-06

Type: script precheck across 3 seed groups. Browser validation still required.

## Main Changes

- Reduced basic 盈蓄 fuel: `surplus_charge_effect` now adds 1 盈蓄 instead of 2.
- Limited field Esper reactivation to 1 prepared reactivation per side per turn.
- Fixed `盈蓄税` so it no longer triggers the 创生 delay-refund card generation.
- Changed 潮汐站台 into a comeback trait: a side only gets the reveal +1 when it was not leading before the reveal, capped at 3 cards per side per turn.

## Three-Seed Average Scores

| Deck | Average | Samples |
| --- | ---: | --- |
| 创生 | 92.3 | 93.0 / 88.0 / 96.0 |
| 延滞 | 90.5 | 89.5 / 93.0 / 89.0 |
| 浊燃 | 92.2 | 93.5 / 93.5 / 89.5 |
| 黯星 | 96.0 | 96.0 / 96.0 / 96.0 |
| 盈蓄 | 94.3 | 93.0 / 96.0 / 94.0 |
| 失谐 | 92.8 | 92.0 / 93.5 / 93.0 |

## Three-Seed Margin Check

| Match | Margins | Average |
| --- | --- | ---: |
| 创生 vs 延滞 | 26 / 6 / 17 | 16.3 |
| 延滞 vs 浊燃 | 1 / 3 / 25 | 9.7 |
| 浊燃 vs 黯星 | 18 / 7 / 10 | 11.7 |
| 黯星 vs 盈蓄 | 14 / 37 / 10 | 20.3 |
| 盈蓄 vs 失谐 | 3 / 25 / 5 | 11.0 |
| 失谐 vs 创生 | 11 / 36 / 8 | 18.3 |

Overall average margin: 14.6. Maximum observed margin: 37.

## Current Assessment

- 中前期博弈 is now visible: turn-2/turn-3 pressure can remove positive-power materials and stop or delay Esper lines.
- 异能者登场 succeeds often, but the opponent can still disrupt by reducing materials to non-positive power.
- 盈蓄 still has the most explosive high-rolls, but no longer self-feeds from its own tax loop.
- 黯星 now plays closer to the intended shape: early setup, late burst, with capped wipe potential.
- 失谐 has a real anti-wide-board punish and can beat sticky 创生 in some environments.

## Browser Validation Focus

- Confirm UI correctly exposes single main battlefield and capped/comeback 潮汐 text.
- Confirm the backend rejection message for a second same-turn field Esper reactivation is clear enough.
- Confirm material shortage and non-positive material destruction are visible in logs.
- Play the 6 fixed pairings in the browser and preserve a final browser report.

