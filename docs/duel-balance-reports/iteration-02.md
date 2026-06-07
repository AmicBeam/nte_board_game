# Iteration 02 - First Balance Pass

Date: 2026-06-06

Type: script precheck. Browser validation was not run in this iteration.

## Main Changes

- Fixed script log accounting for newest-first logs.
- Reworked single-battlefield fallbacks for 早雾, 翳, and 哈尼娅 style spread effects.
- Changed 早雾 to use its intended `zaowu_murk_spread` effect.
- Improved 浊燃 early material curve by making `失纬棋子` a 咒素材 and raising `失落甲胄` to 4 power.
- Added 黯星 low-cost star-shell protection on `环石` and `黑钥匙` only.
- Fixed 法帝娅 and 哈尼娅 to use their intended unique effects instead of generic item effects.
- Changed 黯星爆发 to scale by phase: early turns are lighter, turn 5 onward is capped burst damage.
- Fixed 小吱 and 埃德嘉 to use their intended 盈蓄 resource-link effects.
- Strengthened 失谐 lock against over-wide boards.
- Fixed 哈索尔, 翳, and 卡厄斯 to use their intended 延滞 effects.

## Single-Seed Result

| Match | Result |
| --- | --- |
| 创生 vs 延滞 | 创生 64 - 38 延滞 |
| 延滞 vs 浊燃 | 36 - 36 draw |
| 浊燃 vs 黯星 | 浊燃 30 - 44 黯星 |
| 黯星 vs 盈蓄 | 黯星 32 - 29 盈蓄 |
| 盈蓄 vs 失谐 | 盈蓄 51 - 30 失谐 |
| 失谐 vs 创生 | 失谐 53 - 42 创生 |

## Findings

- 浊燃 now reliably reaches turn-3 Esper play and can pressure opponent materials.
- 黯星 can survive early pressure and still has a recognizable late burst.
- 盈蓄 became fun and high-action, but had extreme high-rolls in 潮汐站台.
- 失谐 improved against wide boards but still needed help against extreme 盈蓄 chains.

## Next Changes

- Reduce extreme 盈蓄 fuel.
- Rework 潮汐站台 from a snowball buff into a comeback-style battlefield trait.
- Prevent 盈蓄税 from incorrectly triggering 创生's delay-refund clause.

