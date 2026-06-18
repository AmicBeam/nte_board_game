import importlib
import pkgutil
from copy import deepcopy
from functools import lru_cache
from types import ModuleType
from typing import Any

from app.content import characters, items
from app.content.common.constants import (
    CARD_TYPE_ANOMALY_ITEM,
    CARD_TYPE_ESPER,
    MAX_DECK_SIZE,
    MAX_ESPER_CARDS_PER_DECK,
    MIN_DECK_SIZE,
)
from app.content.common.tokens import TOKEN_CARDS
from app.content.duel_decks import DUEL_DECKS


def _load_from_package(package: ModuleType, attribute_name: str) -> tuple[dict[str, Any], ...]:
    results: list[dict[str, Any]] = []
    for module_info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f'{package.__name__}.{module_info.name}')
        payload = getattr(module, attribute_name, None)
        if payload is not None:
            if isinstance(payload, (list, tuple)):
                results.extend(deepcopy(list(payload)))
            else:
                results.append(deepcopy(payload))
    return tuple(results)


@lru_cache(maxsize=1)
def _cached_characters() -> tuple[dict[str, Any], ...]:
    return tuple(sorted(_load_from_package(characters, 'CHARACTER'), key=lambda item: item['id']))


def load_characters() -> list[dict[str, Any]]:
    return deepcopy(list(_cached_characters()))


@lru_cache(maxsize=1)
def _cached_items() -> tuple[dict[str, Any], ...]:
    return tuple(sorted(_load_from_package(items, 'ITEM'), key=lambda item: item['id']))


def load_items() -> list[dict[str, Any]]:
    return deepcopy(list(_cached_items()))


@lru_cache(maxsize=1)
def _cached_duel_cards() -> tuple[dict[str, Any], ...]:
    return tuple(sorted(
        [*_cached_items(), *_cached_characters()],
        key=lambda card: (str(card.get('archetype', '')), int(card['cost']), str(card['name'])),
    ))


def load_duel_cards() -> list[dict[str, Any]]:
    return deepcopy(list(_cached_duel_cards()))


@lru_cache(maxsize=1)
def _cached_duel_card_index() -> dict[str, dict[str, Any]]:
    return {str(card['id']): card for card in _cached_duel_cards()}


def get_duel_card(card_id: str) -> dict[str, Any] | None:
    normalized = str(card_id or '').strip()
    if normalized in TOKEN_CARDS:
        return deepcopy(TOKEN_CARDS[normalized])
    definition = _cached_duel_card_index().get(normalized)
    return deepcopy(definition) if definition is not None else None


def clear_content_cache() -> None:
    _cached_characters.cache_clear()
    _cached_items.cache_clear()
    _cached_duel_cards.cache_clear()
    _cached_duel_card_index.cache_clear()


def load_duel_decks() -> list[dict[str, Any]]:
    return [deepcopy(deck) for deck in DUEL_DECKS]


def get_duel_deck(deck_id: str) -> dict[str, Any] | None:
    normalized = str(deck_id or '').strip()
    return next((deck for deck in load_duel_decks() if deck['id'] == normalized), None)


def default_duel_deck_id() -> str:
    return str(DUEL_DECKS[0]['id'])


def validate_duel_deck_card_ids(card_ids: list[str]) -> tuple[bool, str]:
    item_count = 0
    esper_count = 0
    item_copies: dict[str, int] = {}
    seen_espers: set[str] = set()
    for card_id in card_ids:
        definition = get_duel_card(card_id)
        if definition is None:
            return False, '牌组中包含未知卡牌。'
        if definition.get('deck_buildable') is False:
            return False, f"「{definition.get('name', '该卡牌')}」不能放入构筑。"
        card_type = definition.get('type')
        if card_type == CARD_TYPE_ANOMALY_ITEM:
            item_count += 1
            item_copies[card_id] = int(item_copies.get(card_id, 0)) + 1
            if item_copies[card_id] > 3:
                return False, '同名异象道具最多携带 3 张。'
        elif card_type == CARD_TYPE_ESPER:
            if card_id in seen_espers:
                return False, '异能者编队不能携带重复角色。'
            seen_espers.add(card_id)
            esper_count += 1
        else:
            return False, '临时牌不能放入构筑。'
    if item_count < MIN_DECK_SIZE:
        return False, f'异象道具至少携带 {MIN_DECK_SIZE} 张。'
    if item_count > MAX_DECK_SIZE:
        return False, f'异象道具最多携带 {MAX_DECK_SIZE} 张。'
    if esper_count > MAX_ESPER_CARDS_PER_DECK:
        return False, f'一套卡组最多只能携带 {MAX_ESPER_CARDS_PER_DECK} 张异能者卡牌。'
    return True, ''
