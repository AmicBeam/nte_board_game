from flask import Blueprint, g, jsonify, redirect, render_template, request, url_for

from app.auth import login_with_code, token_required
from app.dao import is_tutorial_completed, mark_tutorial_completed, update_player_nickname, update_player_password
from app.engine.game_service import (
    cancel_target,
    choose_cards,
    choose_target,
    end_turn,
    get_catalog_payload,
    get_encyclopedia_payload,
    move_staged_card,
    play_card,
    play_esper,
    return_staged_card,
    retreat,
    save_build,
    undo_turn,
)
from app.errors import AppError
from app.room_service import (
    create_or_resume_solo_room,
    create_room_for_player,
    get_current_room_run_state,
    get_current_room_state,
    join_room_by_code,
    reset_current_room_run,
    set_room_ready,
    start_room_game,
)
from app.utils.logger import get_logger

logger = get_logger('nte.routes')
main_bp = Blueprint('main', __name__)


def _preteam_avatar(filename: str) -> str:
    return f'images/characters/avatar/{filename}'


PRETEAM_MAIN_CANDIDATES: list[dict[str, object]] = [
    {'id': 'nanali', 'name': '娜娜莉', 'image': _preteam_avatar('娜娜莉.png'), 'elem': '灵', 'char_key': 'nanali'},
    {'id': 'xiaozhi', 'name': '小吱', 'image': _preteam_avatar('小吱.png'), 'elem': '光', 'char_key': 'xiaozhi'},
    {'id': 'baicang', 'name': '白藏', 'image': _preteam_avatar('白藏.png'), 'elem': '咒', 'char_key': 'baicang'},
    {'id': 'requiem', 'name': '安魂曲', 'image': _preteam_avatar('安魂曲.png'), 'elem': '暗', 'char_key': 'requiem'},
    {'id': 'hasuoerM', 'name': '哈索尔', 'image': _preteam_avatar('哈索尔.png'), 'elem': '相', 'char_key': 'hasuoer'},
    {'id': 'haiyue', 'name': '海月', 'image': _preteam_avatar('海月.png'), 'elem': '魂', 'char_key': 'haiyue'},
    {'id': 'bohe', 'name': '薄荷', 'image': _preteam_avatar('薄荷.png'), 'elem': '灵', 'char_key': 'bohe'},
]

PRETEAM_TEAMMATES: list[dict[str, object]] = [
    {'id': 'zhujue', 'name': '主角', 'image': _preteam_avatar('鉴定师.png'), 'elem': '光', 'char_key': 'zhujue'},
    {'id': 'xun', 'name': '浔', 'image': _preteam_avatar('浔.png'), 'elem': '光', 'char_key': 'xun'},
    {'id': 'aidejia', 'name': '埃德嘉', 'image': _preteam_avatar('埃德嘉.png'), 'elem': '光', 'char_key': 'aidejia'},
    {'id': 'jiuyuan', 'name': '九原', 'image': _preteam_avatar('九原.png'), 'elem': '灵', 'char_key': 'jiuyuan'},
    {'id': 'boheT', 'name': '薄荷', 'image': _preteam_avatar('薄荷.png'), 'elem': '灵', 'char_key': 'bohe'},
    {'id': 'nanaliT', 'name': '娜娜莉', 'image': _preteam_avatar('娜娜莉.png'), 'elem': '灵', 'char_key': 'nanali'},
    {'id': 'zaowu', 'name': '早雾', 'image': _preteam_avatar('早雾.png'), 'elem': '咒', 'char_key': 'zaowu'},
    {'id': 'adele', 'name': '阿德勒', 'image': _preteam_avatar('阿德勒.png'), 'elem': '咒', 'char_key': 'adele'},
    {'id': 'dafutier0', 'name': '达芙蒂尔', 'image': _preteam_avatar('达芙蒂尔.png'), 'elem': '暗', 'char_key': 'dafutier'},
    {'id': 'fatiya', 'name': '法帝娅', 'image': _preteam_avatar('法帝娅.png'), 'elem': '魂', 'char_key': 'fatiya'},
    {'id': 'haniya', 'name': '哈尼娅', 'image': _preteam_avatar('哈尼娅.png'), 'elem': '魂', 'char_key': 'haniya'},
    {'id': 'hasuoer', 'name': '哈索尔', 'image': _preteam_avatar('哈索尔.png'), 'elem': '相', 'char_key': 'hasuoer'},
    {'id': 'yiT', 'name': '翳', 'image': _preteam_avatar('翳.png'), 'elem': '相', 'char_key': 'yi'},
]


@main_bp.get('/')
def default_page():
    return redirect(url_for('main.login_page'))


@main_bp.get('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='images/brand/duel-icon.webp'))


@main_bp.get('/home')
def home():
    return render_template('index.html')


@main_bp.get('/login')
def login_page():
    return render_template('login.html')


@main_bp.get('/profile')
def profile_page():
    return render_template('profile.html')


@main_bp.get('/build')
def build_page():
    return render_template('build.html')


@main_bp.get('/codex')
def codex_page():
    return render_template('codex.html')


@main_bp.get('/table')
def table_page():
    return render_template('table.html')


@main_bp.get('/preteam')
def preteam_page():
    return render_template(
        'preteam.html',
        main_candidates=PRETEAM_MAIN_CANDIDATES,
        teammates=PRETEAM_TEAMMATES,
    )


@main_bp.post('/api/auth/login')
def api_login():
    payload = request.get_json(silent=True) or {}
    try:
        result, error = login_with_code(str(payload.get('player_uid', '')).strip(), str(payload.get('code', '')).strip())
        if error:
            return jsonify({'error': error}), 400
        return jsonify(result)
    except Exception:
        logger.exception('api_login failed')
        return jsonify({'error': '登录过程中发生异常，请稍后重试。'}), 500


@main_bp.get('/api/me')
@token_required
def api_me():
    return jsonify({
        'player_uid': g.current_player.player_uid,
        'nickname': g.current_player.nickname or g.current_player.player_uid,
    })


@main_bp.post('/api/account/profile')
@token_required
def api_update_profile():
    payload = request.get_json(silent=True) or {}
    try:
        player = update_player_nickname(g.current_player, str(payload.get('nickname', '')))
        return jsonify({
            'player_uid': player.player_uid,
            'nickname': player.nickname or player.player_uid,
        })
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_update_profile failed')
        return jsonify({'error': '修改用户名时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/account/password')
@token_required
def api_update_password():
    payload = request.get_json(silent=True) or {}
    try:
        update_player_password(g.current_player, str(payload.get('password', '')))
        return jsonify({'ok': True})
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_update_password failed')
        return jsonify({'error': '修改密码时发生异常，请稍后重试。'}), 500


@main_bp.get('/api/tutorial/status')
@token_required
def api_tutorial_status():
    try:
        scope = str(request.args.get('scope', ''))
        return jsonify({
            'scope': scope,
            'completed': is_tutorial_completed(g.current_player, scope),
        })
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_tutorial_status failed')
        return jsonify({'error': '读取教学状态时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/tutorial/complete')
@token_required
def api_tutorial_complete():
    payload = request.get_json(silent=True) or {}
    try:
        record = mark_tutorial_completed(g.current_player, str(payload.get('scope', '')))
        return jsonify({
            'scope': record.scope,
            'completed': record.completed,
        })
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_tutorial_complete failed')
        return jsonify({'error': '保存教学状态时发生异常，请稍后重试。'}), 500


@main_bp.get('/api/catalog')
@token_required
def api_catalog():
    try:
        return jsonify(get_catalog_payload(g.current_player))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_catalog failed')
        return jsonify({'error': '读取图鉴与构筑信息时发生异常，请稍后重试。'}), 500


@main_bp.get('/api/encyclopedia')
@token_required
def api_encyclopedia():
    return jsonify(get_encyclopedia_payload())


@main_bp.post('/api/build/save')
@token_required
def api_save_build():
    payload = request.get_json(silent=True) or {}
    try:
        item_ids = payload.get('item_ids')
        if item_ids is None:
            item_ids = [
                *(payload.get('starter_item_ids') or []),
                *(payload.get('reserve_item_ids') or []),
            ]
        result = save_build(
            g.current_player,
            payload.get('character_id', ''),
            item_ids,
            payload.get('esper_card_ids', []),
        )
        return jsonify(result)
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_save_build failed')
        return jsonify({'error': '保存构筑时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/start')
@token_required
def api_start_game():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(create_or_resume_solo_room(g.current_player, payload))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_start_game failed')
        return jsonify({'error': '开始对局时发生异常，请稍后重试。'}), 500


@main_bp.get('/api/game/state')
@token_required
def api_game_state():
    try:
        state = get_current_room_run_state(g.current_player)
        if state is None:
            if request.args.get('optional') == '1':
                return jsonify({'status': 'none', 'has_active_run': False})
            return jsonify({'error': '当前没有对局，请先开始。'}), 404
        return jsonify(state)
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_game_state failed')
        return jsonify({'error': '读取对局状态时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/play-card')
@token_required
def api_play_card():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(play_card(
            g.current_player,
            str(payload.get('card_instance_id', '')),
            str(payload.get('location_id', '')),
        ))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_play_card failed')
        return jsonify({'error': '出牌时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/play-esper')
@token_required
def api_play_esper():
    payload = request.get_json(silent=True) or {}
    material_instance_ids = payload.get('material_instance_ids')
    if material_instance_ids is not None and not isinstance(material_instance_ids, list):
        material_instance_ids = []
    try:
        return jsonify(play_esper(
            g.current_player,
            str(payload.get('card_instance_id', '')),
            str(payload.get('location_id', '')),
            material_instance_ids,
        ))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_play_esper failed')
        return jsonify({'error': '唤醒异能者时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/return-card')
@token_required
def api_return_card():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(return_staged_card(
            g.current_player,
            str(payload.get('card_instance_id', '')),
        ))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_return_card failed')
        return jsonify({'error': '收回卡牌时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/move-card')
@token_required
def api_move_card():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(move_staged_card(
            g.current_player,
            str(payload.get('card_instance_id', '')),
            str(payload.get('location_id', '')),
        ))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_move_card failed')
        return jsonify({'error': '移动卡牌时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/choose-target')
@token_required
def api_choose_target():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(choose_target(
            g.current_player,
            str(payload.get('target_instance_id', '')),
        ))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_choose_target failed')
        return jsonify({'error': '选择目标时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/cancel-target')
@token_required
def api_cancel_target():
    try:
        return jsonify(cancel_target(g.current_player))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_cancel_target failed')
        return jsonify({'error': '取消目标时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/choose-cards')
@token_required
def api_choose_cards():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(choose_cards(
            g.current_player,
            payload.get('card_instance_ids', []),
        ))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_choose_cards failed')
        return jsonify({'error': '选择卡牌时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/end-turn')
@token_required
def api_end_turn():
    try:
        return jsonify(end_turn(g.current_player))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_end_turn failed')
        return jsonify({'error': '结束回合时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/retreat')
@token_required
def api_retreat():
    try:
        return jsonify(retreat(g.current_player))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_retreat failed')
        return jsonify({'error': '撤退时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/undo-turn')
@token_required
def api_undo_turn():
    try:
        return jsonify(undo_turn(g.current_player))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_undo_turn failed')
        return jsonify({'error': '撤销本回合操作时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/reset')
@token_required
def api_reset():
    try:
        reset_current_room_run(g.current_player)
        return jsonify({'ok': True})
    except Exception:
        logger.exception('api_reset failed')
        return jsonify({'error': '重置对局时发生异常，请稍后重试。'}), 500


@main_bp.get('/api/room/state')
@token_required
def api_room_state():
    try:
        room_state = get_current_room_state(g.current_player)
        if room_state is None:
            return jsonify({'error': '当前没有房间。'}), 404
        return jsonify(room_state)
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_room_state failed')
        return jsonify({'error': '读取房间状态时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/room/create')
@token_required
def api_create_room():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(create_room_for_player(g.current_player, str(payload.get('mode', 'solo'))))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_create_room failed')
        return jsonify({'error': '创建房间时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/room/join')
@token_required
def api_join_room():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(join_room_by_code(g.current_player, str(payload.get('room_code', ''))))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_join_room failed')
        return jsonify({'error': '加入房间时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/room/ready')
@token_required
def api_room_ready():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(set_room_ready(g.current_player, bool(payload.get('is_ready', True))))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_room_ready failed')
        return jsonify({'error': '更新准备状态时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/room/start')
@token_required
def api_room_start():
    try:
        return jsonify(start_room_game(g.current_player))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_room_start failed')
        return jsonify({'error': '开始房间游戏时发生异常，请稍后重试。'}), 500
