import random
from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_PASS, add_action_step, add_item_to_hand, add_map_log
from app.engine.events import GameEvent
from app.engine.identification import grant_identification_success

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def access_card_spot_identify(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if tile.get('resolved'):
        return
    chance = float(tile.get('chance', 0.05))
    if random.random() > chance:
        return
    tile['resolved'] = True
    add_item_to_hand(context.state, 'keycard')
    message = '鉴别获得 1 张经理门禁卡。'
    add_map_log(context, message)
    add_action_step(context.state, {
        'type': 'popup',
        'icon': '/static/images/map_object/RobBankItem_G022.webp',
        'title': '经理门禁卡',
        'message': message,
    })
    grant_identification_success(context, definition_id='keycard', source_name='鉴别门禁卡')
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {'object_id': context.payload['object_id'], 'object_type': context.payload['tile_type']})


MAP_OBJECT = {
    'id': 'access_card_spot',
    'icon': '/static/images/map_object/RobBankItem_G022.webp',
    'block_type': BLOCK_TYPE_PASS,
    'identify_on_pass': True,
    'tooltip': '经理门禁卡：鉴别后获得 1 张经理门禁卡。',
    'event_hooks': {
        GameEvent.IDENTIFY.value: access_card_spot_identify,
    },
}
