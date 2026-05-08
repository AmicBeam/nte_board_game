from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from app.content.loader import get_item


@dataclass
class CharacterInstance:
    instance_id: str
    definition_id: str
    name: str
    title: str
    passive: str
    max_hp: int
    attack: int
    defense: int


@dataclass
class ItemInstance:
    instance_id: str
    definition_id: str
    zone: str
    created_turn: int


def build_character_instance(character_definition: dict[str, Any]) -> dict[str, Any]:
    return asdict(CharacterInstance(
        instance_id=uuid4().hex,
        definition_id=character_definition['id'],
        name=character_definition['name'],
        title=character_definition['title'],
        passive=character_definition['passive'],
        max_hp=character_definition['max_hp'],
        attack=character_definition['attack'],
        defense=character_definition['defense'],
    ))


def build_item_instances(item_ids: list[str], turn: int = 1) -> list[dict[str, Any]]:
    item_instances: list[dict[str, Any]] = []
    for item_id in item_ids:
        item_instances.append(asdict(ItemInstance(
            instance_id=uuid4().hex,
            definition_id=item_id,
            zone='hand',
            created_turn=turn,
        )))
    return item_instances


def serialize_item_definition(item_definition: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(item_definition)
    payload.pop('event_hooks', None)
    payload.pop('runtime_effects', None)
    return payload


def serialize_item_instance(item_instance: dict[str, Any]) -> dict[str, Any] | None:
    definition = deepcopy(get_item(item_instance['definition_id']))
    if definition is None:
        return None
    payload = serialize_item_definition(definition)
    payload['instance_id'] = item_instance['instance_id']
    return payload
