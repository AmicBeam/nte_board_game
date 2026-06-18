---
name: nte-card-effect-design
description: Use when designing, reviewing, or revising NTE / Everness 异象对决 card effects, card descriptions, archetype documents, or content files under app/content/items and app/content/characters. Applies to terminology, declaration/targeting wording, reveal/resonance timing, harmony markers, item/esper effect clarity, and avoiding non-rules terms such as “延滞道具” or “xx件”.
---

# NTE Card Effect Design

Use this skill to write card effects that can be understood by players and implemented by the backend without hidden intent.

## Workflow

1. Read `docs/everness-item-chain-card-design.md` first; it is the design source of truth.
2. Preserve existing archetype identity when revising. Add new特色 to the original design理念 instead of replacing it.
3. Write effects with visible card fields: card name, attribute, category, cost, current power, zone, face-up state, and named markers.
4. For every effect, check timing, target selection, invalid target behavior, and whether the text asks the player to choose more than once.
5. If implementing after document work, keep card `description`, `declaration`, and effect code in sync.

## Allowed Terms

Use these terms directly when they match the rule:

- Card types: `异象道具`, `异能者`, `衍生牌`.
- Timing: `宣言`, `揭示`, `诱发`, `共鸣`, `再共鸣`, `设置环合`, `持续一回合`, `本回合`.
- Zones: `牌库`, `手牌`, `墓地`, `战场`, `异能者编队`.
- Visibility and state: `表侧`, `背面`, `部署中`, `稳定在场`, `破碎`.
- Stats and resources: `费用`, `当前战力`, `基础战力`, `可用能量`, `下次部署费用 -1`.
- Attributes: `光`, `灵`, `相`, `咒`, `暗`, `魂`.
- Categories: real item categories such as `食物`, `食材`, `饮料`, `礼物`, `耗材`, `材料`, `货币`, `家具`, `任务`, `钓鱼`, `重要`, `其他`.
- Harmony and fusion: `创生`, `延滞`, `浊燃`, `黯星`, `盈蓄标记`, `失谐标记`, `盈蓄牌`.
- Actions: `从牌库加入手牌`, `从墓地返回手牌`, `从牌库置入墓地`, `部署`, `返回手牌`, `生成`, `获得护盾`, `战力 +X/-X`, `战力减半，向下取整`.
- Build restriction: use `不可构筑` as a separate display tag for generated or special cards that can enter hand/deck/grave during a match but cannot be selected in deckbuilding. Do not put this restriction inside effect text.

Use card names in Chinese corner quotes: `「都市活力」`, `「本性像素」`.

## Avoid These Terms

Do not use non-field shorthand as player-facing rules:

- `创生道具`, `延滞道具`, `浊燃道具`, `黯星道具`.
- `xx件`, `专属件`, `盈蓄件`, `失谐件`, `材料件`.
- `低战力` or `高战力` without a precise selector.
- `使用` as a card timing term; use `揭示` for anomaly item resolution.
- `己方回合` or `对手回合` for duration; use `本回合` or `持续一回合`.
- Vague phrases such as `再使另一个`, `触发相关收益`, or `影响对手关键牌`.

Replace shorthand with fields:

- Bad: `随机从牌库将 1 张费用 <=2 的延滞道具加入手牌。`
- Good: `随机从牌库将 1 张费用 <=2 且属性为光或相的异象道具加入手牌。`

## Targeting

If the player chooses a target, write a `宣言` step. Reveal only executes the declared choice.

- Board target: include `表侧` and side, such as `宣言：选择 1 张对手表侧道具。`
- Deck, hand, or grave target: write `宣言：检视牌库/墓地/手牌，选择...`.
- If the target may become illegal, add or imply `若宣言对象不再合法，该部分不结算`.
- Avoid multiple inspections or multiple target declarations on one card. If a second object is needed, make it random or automatic.

If there is no player choice, write the selector explicitly:

- `随机选择 1 张...`
- `当前战力最高的表侧单位`
- `当前战力最低的表侧道具`
- `未被此效果影响的敌方表侧单位`

When using `另 1 张` or `另一张`, define the exclusion:

- Bad: `再使另一个敌方单位 -2。`
- Good: `随机选择 1 张未被此效果影响的敌方表侧单位，使其 -2；若没有其他合法单位，该部分不结算。`

## Timing Boundaries

`揭示` happens after both players finish the deployment stage. Reveal effects can read deployment records, material-consumption records, and already resolved reveal effects, but they should not try to retroactively change deployment-stage costs or choices.

- Do not write reveal effects that make the opponent pay extra for an action that would already have happened during the deployment/material declaration stage.
- If a reveal effect affects a future action, say the future window clearly, such as `对手下回合可用能量 -1` or `宣言道具下次部署费用 -1`.
- If a deployment-stage restriction is needed, make it a declaration/reservation rule that is checked before deployment ends, not a reveal-time surprise.

## Trigger Clarity

Do not write redundant trigger text when the first action already causes the trigger.

- Bad: `将宣言材料置入墓地，并额外触发其“从牌库置入墓地时”收益。`
- Good: `将宣言材料置入墓地。`

Use `诱发：` only for effects that wait for a clearly named future event, such as `诱发：回合结束时...`.

## Effect Shape

Prefer one main choice and one clear payoff:

```text
宣言：选择 1 张己方表侧耗材道具。
揭示：将宣言道具返回手牌并使其下次部署费用 -1；随后随机从牌库或墓地将 1 张费用 <=2 的耗材道具加入手牌。
```

For extra effects, specify exactly what receives the bonus:

- `自身 +1`
- `宣言道具下次部署费用 -1`
- `随机选择 1 张未被此效果影响的敌方表侧单位，使其 -2`

For conditions, state the readable condition and failure mode when needed:

- `若己方至少两个区域存在「本性像素」...`
- `若没有其他合法单位，该部分不结算。`

## Review Checklist

Before finalizing a card effect:

1. Does every chosen target have a `宣言`?
2. Does every non-chosen target say `随机` or use a precise automatic selector?
3. Are all affected battlefield cards explicitly `表侧` when relevant?
4. Are categories and attributes real fields instead of archetype slang?
5. Is there at most one inspection/selection sequence unless the complexity is essential?
6. Is any trigger text redundant with an action already performed?
7. Does the text preserve the archetype's original role while adding new特色?
