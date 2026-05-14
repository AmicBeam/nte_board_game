---
name: sketch-to-map-template
description: Convert annotated floor-plan sketches, screenshots, or user-provided wall arrays into compact tile-map JSON templates for 2D grid games. Use when Codex needs to trace room outlines, preserve wall paths, assign legend symbols, place doors, portals, random loot points, safes, or monster spawn points, and migrate a hand-drawn map into a validated content-map JSON file.
---

# Sketch To Map Template

## Workflow

1. Treat the wall outline as the source of truth. If the user provides a character array, preserve every row and column exactly; if the user provides an image, trace the visible wall lines first and defer content placement until the outline matches the sketch.
2. Normalize each layer independently: choose one tile size per layer, trim all outer all-space rows/columns, keep rows rectangular inside that layer, and derive `width`, `height`, and layer count from the `tiles` arrays instead of requiring top-level fields.
3. Use a compact `tiles` matrix plus a `legend` dictionary. Each non-floor symbol should explain behavior with `type` and only the parameters that type needs. Omit `object_id` when it is the same as `type`; the loader supplies that at runtime.
4. Keep authoring landmarks separate from runtime objects. A desk drawn in a sketch is usually an authoring cue for a `type=random` tile; it should transform into a loot item or floor through a loot table unless the game explicitly has a visible desk object.
5. Put item identity, icon, value, tooltip, and behavior in item or map-object definitions. The map JSON should reference loot table IDs, monster definition IDs, and portal targets; use `object_id` only when the handling module intentionally differs from `type`.
6. Model probability with loot tables. A random tile can transform into a collectible, safe, large safe, or floor by selecting an object entry from its referenced table. Do not overlay random loot on top of an existing tile.
7. Place monsters by symbols in the matrix. Monster definitions should contain stats and drop tables, not coordinates already encoded by the tile matrix.
8. Validate before editing further: every row in a layer has that layer’s width, no layer has all-space outer margins, every symbol appears in `legend`, at least one symbol maps to `type=entry`, loot table entries are objects, and no map JSON subtree contains `icon`.

## NTE Map Conventions

Use these conventions when working in `nte_board_game` unless the local code says otherwise:

- `M`: wall.
- `E`: entry point (`type=entry`); do not also maintain a top-level `start`.
- `D`: normal locked door; `d`: hidden door; `v`: keycard door when the sketch marks a manager/card door.
- `P` and `Q`: portal endpoints with explicit target coordinates.
- `r`: random desk-origin loot point. For the RobBank office sketch, this must only become collectible loot or floor, not safes.
- `s`: random small-safe spawn point; `V`: random large-safe spawn point.
- `c`: surveillance camera monster spawn.
- `B`: boss footprint on a boss layer.

When a sketch shows many repeated furniture shapes, sample representative points rather than filling every shape. Favor readable gameplay spacing and never place content on walls, doors, portals, the start tile, or boss tiles.

## Validation Helper

Run the bundled checker when a map JSON uses compact tile layers:

```bash
python3 /Users/bytedance/.codex/skills/sketch-to-map-template/scripts/validate_tile_grid.py app/content/maps/rob_bank.json
```

The checker derives per-layer dimensions from `tiles`, validates legend coverage, requires an entry symbol, checks icon-free map data, checks loot table object entries, and checks coordinate-free monster definitions.
