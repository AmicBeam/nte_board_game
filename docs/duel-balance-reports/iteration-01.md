# Iteration 01 - Script Baseline

Date: 2026-06-06

Type: script precheck. Browser validation was not run in this iteration.

## Baseline Scores

| Deck | Score | Notes |
| --- | ---: | --- |
| 创生 | 75.5 | Sticky beginner curve worked, but was overrepresented by raw board stability. |
| 延滞 | 64.5 | Control existed but did not consistently stop key Esper turns. |
| 浊燃 | 56.0 | Lowest. Often failed to awaken an Esper by turn 3. |
| 黯星 | 59.0 | Could explode, but early pressure windows were uneven. |
| 盈蓄 | 62.0 | High action potential existed, but interaction metrics were inconsistent. |
| 失谐 | 64.5 | Control shell existed, but empty-board fantasy was not reliable. |

## Findings

- 浊燃 early materials did not reliably line up with 咒 Esper requirements.
- 早雾 had a single-battlefield mismatch: its spread-style design had no usable adjacent spaces.
- Script logging undercounted Esper and interaction events because combat logs are stored newest-first and capped.
- 单战场 reduced slot pressure, but old adjacent-space effects needed conversion.

## Changes Planned

- Fix evaluator log capture and increase script log cap during prechecks.
- Make 浊燃 early curve provide enough 咒 materials.
- Convert adjacent-space effects into current-main-battlefield effects where needed.

