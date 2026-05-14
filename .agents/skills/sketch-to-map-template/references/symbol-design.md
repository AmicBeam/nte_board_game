# Symbol Design Notes

Use symbols to encode authoring intent, not asset identity. A symbol should map to a small structured legend entry such as `type=random`, `loot_table_id=desk`, or `monster_id=surveillance_camera`.

Do not put icons in map JSON. Icons belong to item definitions, map-object definitions, or frontend fallback rendering.

For random points, prefer table entries like:

```json
{"weight": 1, "result": {"type": "large_safe", "object_id": "large_safe", "loot_table_id": "large_safe"}}
```

or item entries like:

```json
{"item_id": "cash", "weight": 4}
```

Include `{"weight": N, "result": {"type": "floor"}}` when a random point may become empty.
