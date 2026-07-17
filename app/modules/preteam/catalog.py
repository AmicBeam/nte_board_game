def _avatar(filename: str) -> str:
    return f'images/characters/avatar/{filename}'


MAIN_CANDIDATES: list[dict[str, object]] = [
    {'id': 'nanali', 'name': '娜娜莉', 'image': _avatar('娜娜莉.webp'), 'elem': '灵', 'char_key': 'nanali'},
    {'id': 'xiaozhi', 'name': '小吱', 'image': _avatar('小吱.webp'), 'elem': '光', 'char_key': 'xiaozhi'},
    {'id': 'baicang', 'name': '白藏', 'image': _avatar('白藏.webp'), 'elem': '咒', 'char_key': 'baicang'},
    {'id': 'requiem', 'name': '安魂曲', 'image': _avatar('安魂曲.webp'), 'elem': '暗', 'char_key': 'requiem'},
    {'id': 'hasuoerM', 'name': '哈索尔', 'image': _avatar('哈索尔.webp'), 'elem': '相', 'char_key': 'hasuoer'},
    {'id': 'haiyue', 'name': '海月', 'image': _avatar('海月.webp'), 'elem': '魂', 'char_key': 'haiyue'},
    {'id': 'bohe', 'name': '薄荷', 'image': _avatar('薄荷.webp'), 'elem': '灵', 'char_key': 'bohe'},
]

TEAMMATES: list[dict[str, object]] = [
    {'id': 'zhujue', 'name': '主角', 'image': _avatar('鉴定师.webp'), 'elem': '光', 'char_key': 'zhujue'},
    {'id': 'xun', 'name': '浔', 'image': _avatar('浔.webp'), 'elem': '光', 'char_key': 'xun'},
    {'id': 'aidejia', 'name': '埃德嘉', 'image': _avatar('埃德嘉.webp'), 'elem': '光', 'char_key': 'aidejia'},
    {'id': 'jiuyuan', 'name': '九原', 'image': _avatar('九原.webp'), 'elem': '灵', 'char_key': 'jiuyuan'},
    {'id': 'boheT', 'name': '薄荷', 'image': _avatar('薄荷.webp'), 'elem': '灵', 'char_key': 'bohe'},
    {'id': 'nanaliT', 'name': '娜娜莉', 'image': _avatar('娜娜莉.webp'), 'elem': '灵', 'char_key': 'nanali'},
    {'id': 'zaowu', 'name': '早雾', 'image': _avatar('早雾.webp'), 'elem': '咒', 'char_key': 'zaowu'},
    {'id': 'adele', 'name': '阿德勒', 'image': _avatar('阿德勒.webp'), 'elem': '咒', 'char_key': 'adele'},
    {'id': 'dafutier0', 'name': '达芙蒂尔', 'image': _avatar('达芙蒂尔.webp'), 'elem': '暗', 'char_key': 'dafutier'},
    {'id': 'fatiya', 'name': '法帝娅', 'image': _avatar('法帝娅.webp'), 'elem': '魂', 'char_key': 'fatiya'},
    {'id': 'haniya', 'name': '哈尼娅', 'image': _avatar('哈尼娅.webp'), 'elem': '魂', 'char_key': 'haniya'},
    {'id': 'hasuoer', 'name': '哈索尔', 'image': _avatar('哈索尔.webp'), 'elem': '相', 'char_key': 'hasuoer'},
    {'id': 'yiT', 'name': '翳', 'image': _avatar('翳.webp'), 'elem': '相', 'char_key': 'yi'},
]
