from flask import Blueprint, g, jsonify, render_template, request

from app.auth import login_with_code, token_required
from app.dao import is_tutorial_completed, mark_tutorial_completed, update_player_nickname, update_player_password
from app.engine.game_service import get_catalog_payload, get_encyclopedia_payload, move_player, play_item, roll_dice, save_build
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


@main_bp.get('/')
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
        result = save_build(g.current_player, payload.get('character_id', ''), payload.get('item_ids', []))
        return jsonify(result)
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_save_build failed')
        return jsonify({'error': '保存构筑时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/start')
@token_required
def api_start_game():
    try:
        return jsonify(create_or_resume_solo_room(g.current_player))
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
            return jsonify({'error': '当前没有对局，请先开始。'}), 404
        return jsonify(state)
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_game_state failed')
        return jsonify({'error': '读取对局状态时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/roll')
@token_required
def api_roll():
    try:
        return jsonify(roll_dice(g.current_player))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_roll failed')
        return jsonify({'error': '掷骰时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/play-item')
@token_required
def api_play_item():
    payload = request.get_json(silent=True) or {}
    try:
        declared_value = payload.get('declared_value')
        return jsonify(play_item(g.current_player, payload.get('item_instance_id', ''), declared_value))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_play_item failed')
        return jsonify({'error': '使用道具时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/move')
@token_required
def api_move():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(move_player(g.current_player, payload.get('direction', ''), payload.get('path')))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_move failed')
        return jsonify({'error': '移动时发生异常，请稍后重试。'}), 500


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
