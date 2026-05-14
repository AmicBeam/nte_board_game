from app.content.map_objects.common import BLOCK_TYPE_PASS


MAP_OBJECT = {
    'id': 'open_door',
    'icon': '/static/images/map_object/push-door.svg',
    'block_type': BLOCK_TYPE_PASS,
    'tooltip': '已开启的门：不会阻挡移动。',
    'tags': ['可通过'],
    'event_hooks': {},
}
