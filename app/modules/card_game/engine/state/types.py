from __future__ import annotations

from typing import Any, Literal, TypeAlias, TypedDict

JsonDict: TypeAlias = dict[str, Any]
SideKey: TypeAlias = Literal['a', 'b']


class BuffSourceState(TypedDict, total=False):
    name: str
    amount: int
    key: str


class CardState(TypedDict, total=False):
    instance_id: str
    definition_id: str
    name: str
    type: str
    cost: int
    cost_modifier: int
    base_power: int
    bonus_power: int
    computed_power: int
    revealed: bool
    staged: bool
    played_turn: int | None
    location_id: str | None
    play_sequence: int
    paid_cost: int
    tags: list[str]
    material_tags: list[str]
    material_attributes: list[str]
    material_cost: int
    material_requirements: list[JsonDict]
    material_requirement_text: str
    required_material_attribute: str
    ai_material_reserved_for: list[str]
    selected_target_instance_id: str
    selected_target_name: str
    declared_card_instance_ids: list[str]
    declared_card_names: list[str]
    pending_material_ids: list[str]
    reserved_as_material_for: str
    reserved_material_power: int
    summoned_from: str
    reactivating_turn: int
    consumed_material_tags: list[str]
    consumed_material_names: list[str]
    consumed_material_attributes: list[str]
    consumed_material_instance_ids: list[str]
    absorbed_material_power: int
    buff_sources: list[BuffSourceState]


class PendingTargetState(TypedDict, total=False):
    source_instance_id: str
    location_id: str
    scope: str
    prompt: str
    candidates: list[JsonDict]


class SelectionState(TypedDict, total=False):
    kind: str
    title: str
    prompt: str
    cards: list[CardState]
    pick_count: int
    source_instance_id: str
    location_id: str


class SideState(TypedDict, total=False):
    side: str
    uid: str
    nickname: str
    is_ai: bool
    deck_id: str
    hand: list[CardState]
    deck: list[CardState]
    discard: list[CardState]
    esper_standby: list[CardState]
    selection: SelectionState | None
    pending_target: PendingTargetState | None
    energy_used: int
    ended_turn: bool
    combo: dict[str, Any]
    ai_plan: JsonDict


class LocationState(TypedDict, total=False):
    id: str
    name: str
    short_name: str
    reveal_turn: int
    revealed: bool
    art: str
    description: str
    effect: str
    cards: dict[str, list[CardState]]
    power: dict[str, int]
    winner_side: str | None
    marks: dict[str, dict[str, int]]
    trait_uses: dict[str, JsonDict]


class ActionPayload(TypedDict, total=False):
    kind: str
    side: str
    title: str
    subtitle: str
    source_instance_id: str
    target_instance_id: str
    location_id: str
    source_location_id: str
    card: JsonDict


class SnapshotState(TypedDict, total=False):
    schema_version: int
    game_id: str
    mode: str
    scenario: str
    scenario_label: str
    status: str
    phase: str
    turn: int
    max_turns: int
    locations: list[LocationState]
    sides: dict[str, SideState]
    winner_side: str | None
    log: list[str]
    action_queue: list[ActionPayload]
    banner_queue: list[ActionPayload]
    play_sequence_counter: int
    token_counter: int
    turn_energy: int
    turn_undo_checkpoints: dict[str, JsonDict]
    settlement: JsonDict
    settlement_first_side: str
