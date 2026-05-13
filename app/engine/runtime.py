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
    passive: str
    portrait_image: str
    avatar_image: str
    max_hp: int
    attack: int
    defense: int
    identification_level: int


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
        passive=character_definition['passive'],
        portrait_image=character_definition.get('portrait_image', f"/static/images/characters/portrait/{character_definition['name']}.png"),
        avatar_image=character_definition.get('avatar_image', f"/static/images/characters/avatar/{character_definition['name']}.png"),
        max_hp=character_definition['max_hp'],
        attack=character_definition['attack'],
        defense=character_definition['defense'],
        identification_level=int(character_definition.get('identification_level', 1)),
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
    payload.setdefault('can_play', True)
    tags = [str(tag) for tag in payload.get('tags', []) if str(tag)]
    if payload.get('type') in {'loot', 'key'} and payload.get('hidden_from_build') and '可鉴别' not in tags:
        tags.append('可鉴别')
    if tags:
        payload['tags'] = tags
    return payload


def serialize_item_instance(item_instance: dict[str, Any]) -> dict[str, Any] | None:
    definition = deepcopy(get_item(item_instance['definition_id']))
    if definition is None:
        return None
    payload = serialize_item_definition(definition)
    payload['instance_id'] = item_instance['instance_id']
    for key in ('amount', 'quantity', 'cooldown_until_turn', 'captured_enemy_id'):
        if key in item_instance:
            payload[key] = item_instance[key]
    return payload
