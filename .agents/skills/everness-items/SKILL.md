---
name: everness-items
description: Fetch Everness / NTE / 异环 item data from everness.info, inspect item descriptions for lore-based item links, and download item icons from the Everness asset CDN. Use when designing 异象道具 cards, checking item names/categories/descriptions/sources, finding worldbuilding links such as 畅爽焕能 -> 都市活力, or syncing item images.
---

# Everness Items

Use this skill when item design must be grounded in current Everness item data instead of invented names or generic effects.

## Quick Start

```bash
python3 .agents/skills/everness-items/scripts/fetch_everness_items.py --name "畅爽焕能"
python3 .agents/skills/everness-items/scripts/fetch_everness_items.py --name "畅爽焕能" --links
python3 .agents/skills/everness-items/scripts/fetch_everness_items.py --name "畅爽焕能" --download-icons app/static/images/item
python3 .agents/skills/everness-items/scripts/fetch_everness_items.py --search "都市 活力" --format json
python3 .agents/skills/everness-items/scripts/fetch_everness_items.py --list-types
```

## Workflow

1. Fetch items with the script instead of guessing item names, categories, descriptions, or images.
2. Prefer `--links` when designing card chains. Treat `explicit_mentions` as the strongest worldbuilding link because it comes from item description/context text.
3. For item icons, use `--download-icons <dir>`. The script converts Everness icon paths such as `/Game/UI/UI_Icon/Item/CityStamina_addpotion` to `https://api.everness.info/data/assets/UI_Icon/Item/CityStamina_addpotion.webp`.
4. When choosing card effects, preserve the item relationship in the text: if one item says it restores or consumes another item/resource, make that the combo chain before adding abstract mechanics.

## Data Notes

- GraphQL endpoint: `https://everness.info/api/graphql`.
- Locale: use `Cookie: locale=zh-Hans` plus Chinese `Accept-Language`.
- Item fields include `id`, `name`, `icon`, `quality`, `type_id`, `type_icon`, `type_custom_id`, `description`, `context`, and `sources`.
- Cached item JSON lives under the OS temp directory for one hour by default.

## Design Rule

For 异象道具, prioritize real item names and lore links from `description` / `context`. Do not invent “xx件”, “盈蓄件”, or “失谐件” categories when Everness item text already gives a better relation.
