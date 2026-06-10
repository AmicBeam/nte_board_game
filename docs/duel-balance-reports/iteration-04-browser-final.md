# Iteration 04 - Browser Final Validation

Date: 2026-06-06

Type: browser validation with real UI actions. The browser automation entered the table from `/home`, selected the trial decks, used hand cards through keyboard focus, selected draw choices, selected Esper materials, attempted field Esper reactivation, ended turns through the UI, and only read `/api/game/state` for reporting.

## Result

The six decks are satisfactory for the current MVP target. The browser run confirms the intended play pattern:

- Early turns are not empty: every deck deployed a 1-cost or 2-cost engine and then chose between more setup, tax, pressure, or removal.
- Esper timing is interactable: 延滞 taxes repeatedly stopped or delayed 创生, 黯星 burst returned 浊燃 Espers to the extra zone, and 失谐/盈蓄 both forced resource-routing decisions.
- Late turns are explosive: 黯星 flipped a losing board, 盈蓄 produced multi-card turns, and 创生 showed a large protected board when not fully locked out.
- The single battlefield reduced slot friction while keeping battlefield traits meaningful.

## Browser Matches

| Match | Browser result | Final power | Key observation |
| --- | --- | ---: | --- |
| 创生 vs 延滞 | 延滞胜 | 49-57 | 创生在 5 回合唤醒浔和娜娜莉，但延滞税与时狱看守吞 3 素材后反超，成功体现“阻止/拖慢异能者”。 |
| 延滞 vs 浊燃 | 浊燃胜 | 9-46 | 浊燃连续压低素材并滚出 8 个浊燃，延滞若前期没锁住节奏会被快速碾开。 |
| 浊燃 vs 黯星 | 黯星胜 | 10-46 | 黯星在后期清掉浊燃素材，阿德勒战力归零返回异能者编队，爆发返场成立。 |
| 黯星 vs 盈蓄 | 盈蓄胜 | 44-56 | 黯星有 44 战力爆发，但盈蓄靠回流与费用魔术越过一波爆点。 |
| 盈蓄 vs 失谐 | 盈蓄胜 | 64-43 | 盈蓄 2-4 回合连续唤醒小吱、埃德嘉、回流经纪人；失谐用黑契/伪记录抹除复利君主但未完全阻断。 |
| 失谐 vs 创生 | 创生胜 | 46-92 | 失谐能打出最后一句控制，但创生后期保护与鉴定师吸素材形成大场面。 |

Screenshots were captured at:

- `/private/tmp/nte-browser-match-1.png`
- `/private/tmp/nte-browser-match-2.png`
- `/private/tmp/nte-browser-match-3.png`
- `/private/tmp/nte-browser-match-4.png`
- `/private/tmp/nte-browser-match-5.png`
- `/private/tmp/nte-browser-match-6.png`

## Deck Scores

| Deck | Score | Assessment |
| --- | ---: | --- |
| 创生 | 90 | 入门节奏清楚，能被延滞拖慢，也能在失谐面前靠保护和大身材终结。调度较少但符合入门定位。 |
| 延滞 | 88 | 费用税和素材吞噬的交互点最清楚；对浊燃高速展开的容错较低，但这是可读的劣势而非失效。 |
| 浊燃 | 91 | 中期压制感很强，能打碎素材和异能者；面对黯星时会被后期爆发惩罚，克制关系明确。 |
| 黯星 | 92 | 前弱后强成立，后期黯星爆发能清场并重建优势；早期星壳让它不再被压死。 |
| 盈蓄 | 93 | 费用魔术和多卡连打最爽，资源操作量最高；已被限速，不再无限自循环。 |
| 失谐 | 87 | 控制体验成立，但自动玩家下对盈蓄/创生仍偏吃力；作为高难控制套牌保留学习空间。 |

Highest-lowest spread: 6. All decks are above the 82 satisfaction threshold.

## Final Balance Call

No further card-structure adjustment is needed in this iteration. The lowest deck is 失谐, but its weakness is mostly pilot difficulty: it needs correctly sequence 抹除、失谐控制 and late high-cost tools. Script prechecks already placed it in the low-90 range, while browser play showed its control effects firing but not always converting to a win.

## UI Findings Fixed During Browser Validation

- Fixed selection overlay recovery after repeated presentation keys so draw choices cannot disappear behind skipped animations.
- Hardened field Esper interaction so revealed player Espers can be clicked for reactivation from the battlefield.
- Browser automation exposed stale-overlay and material-selection races; these were validation-script issues, while the frontend fix above is the lasting product fix.

## Remaining Follow-Up

- Consider adding a clearer UI hint when dynamic taxes make a visually 0-cost Esper unplayable.
- Add a small visible “本次额外费用” indicator near the energy display in a future polish pass.
