from __future__ import annotations

import threading

from flask import Blueprint, g, jsonify, redirect, render_template, request, url_for

from app.auth import login_with_code, token_required
from app.dao import is_tutorial_completed, mark_tutorial_completed, update_player_nickname, update_player_password
from app.engine.game_service import (
    choose_cards,
    declaration_preview,
    declaration_previews,
    end_turn,
    get_catalog_payload,
    get_encyclopedia_payload,
    retreat,
    save_build,
)
from app.engine.application.analytics_service import get_duel_analytics_payload
from app.engine.application.kongmu_service import get_kongmu_catalog_payload, plan_kongmu_layout
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
_kongmu_plan_locks_guard = threading.Lock()
_kongmu_plan_locks: dict[str, threading.Lock] = {}


def _request_source_key() -> str:
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        return forwarded_for.split(',', 1)[0].strip() or 'unknown'
    return request.remote_addr or 'unknown'


def _acquire_kongmu_plan_lock(source_key: str) -> threading.Lock | None:
    with _kongmu_plan_locks_guard:
        lock = _kongmu_plan_locks.setdefault(source_key, threading.Lock())
    if not lock.acquire(blocking=False):
        return None
    return lock


def _preteam_avatar(filename: str) -> str:
    return f'images/characters/avatar/{filename}'


PRETEAM_MAIN_CANDIDATES: list[dict[str, object]] = [
    {'id': 'nanali', 'name': '娜娜莉', 'image': _preteam_avatar('娜娜莉.webp'), 'elem': '灵', 'char_key': 'nanali'},
    {'id': 'xiaozhi', 'name': '小吱', 'image': _preteam_avatar('小吱.webp'), 'elem': '光', 'char_key': 'xiaozhi'},
    {'id': 'baicang', 'name': '白藏', 'image': _preteam_avatar('白藏.webp'), 'elem': '咒', 'char_key': 'baicang'},
    {'id': 'requiem', 'name': '安魂曲', 'image': _preteam_avatar('安魂曲.webp'), 'elem': '暗', 'char_key': 'requiem'},
    {'id': 'hasuoerM', 'name': '哈索尔', 'image': _preteam_avatar('哈索尔.webp'), 'elem': '相', 'char_key': 'hasuoer'},
    {'id': 'haiyue', 'name': '海月', 'image': _preteam_avatar('海月.webp'), 'elem': '魂', 'char_key': 'haiyue'},
    {'id': 'bohe', 'name': '薄荷', 'image': _preteam_avatar('薄荷.webp'), 'elem': '灵', 'char_key': 'bohe'},
]

PRETEAM_TEAMMATES: list[dict[str, object]] = [
    {'id': 'zhujue', 'name': '主角', 'image': _preteam_avatar('鉴定师.webp'), 'elem': '光', 'char_key': 'zhujue'},
    {'id': 'xun', 'name': '浔', 'image': _preteam_avatar('浔.webp'), 'elem': '光', 'char_key': 'xun'},
    {'id': 'aidejia', 'name': '埃德嘉', 'image': _preteam_avatar('埃德嘉.webp'), 'elem': '光', 'char_key': 'aidejia'},
    {'id': 'jiuyuan', 'name': '九原', 'image': _preteam_avatar('九原.webp'), 'elem': '灵', 'char_key': 'jiuyuan'},
    {'id': 'boheT', 'name': '薄荷', 'image': _preteam_avatar('薄荷.webp'), 'elem': '灵', 'char_key': 'bohe'},
    {'id': 'nanaliT', 'name': '娜娜莉', 'image': _preteam_avatar('娜娜莉.webp'), 'elem': '灵', 'char_key': 'nanali'},
    {'id': 'zaowu', 'name': '早雾', 'image': _preteam_avatar('早雾.webp'), 'elem': '咒', 'char_key': 'zaowu'},
    {'id': 'adele', 'name': '阿德勒', 'image': _preteam_avatar('阿德勒.webp'), 'elem': '咒', 'char_key': 'adele'},
    {'id': 'dafutier0', 'name': '达芙蒂尔', 'image': _preteam_avatar('达芙蒂尔.webp'), 'elem': '暗', 'char_key': 'dafutier'},
    {'id': 'fatiya', 'name': '法帝娅', 'image': _preteam_avatar('法帝娅.webp'), 'elem': '魂', 'char_key': 'fatiya'},
    {'id': 'haniya', 'name': '哈尼娅', 'image': _preteam_avatar('哈尼娅.webp'), 'elem': '魂', 'char_key': 'haniya'},
    {'id': 'hasuoer', 'name': '哈索尔', 'image': _preteam_avatar('哈索尔.webp'), 'elem': '相', 'char_key': 'hasuoer'},
    {'id': 'yiT', 'name': '翳', 'image': _preteam_avatar('翳.webp'), 'elem': '相', 'char_key': 'yi'},
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


@main_bp.get('/analytics')
def analytics_page():
    return render_template('analytics.html')


@main_bp.get('/kongmu')
def kongmu_page():
    return render_template('kongmu.html')


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


@main_bp.get('/api/analytics/balance')
@token_required
def api_balance_analytics():
    return jsonify(get_duel_analytics_payload())


@main_bp.get('/api/kongmu/catalog')
def api_kongmu_catalog():
    try:
        return jsonify(get_kongmu_catalog_payload())
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_kongmu_catalog failed')
        return jsonify({'error': '读取空幕数据时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/kongmu/plan')
def api_kongmu_plan():
    payload = request.get_json(silent=True) or {}
    source_key = _request_source_key()
    source_lock = _acquire_kongmu_plan_lock(source_key)
    if source_lock is None:
        return jsonify({'error': '同一来源已有空幕计算正在进行，请稍后再试。'}), 429
    try:
        return jsonify(plan_kongmu_layout(str(payload.get('character_id', '')), str(payload.get('cartridge_id', ''))))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_kongmu_plan failed')
        return jsonify({'error': '计算空幕方案时发生异常，请稍后重试。'}), 500
    finally:
        source_lock.release()


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


@main_bp.get('/api/game/declaration-previews')
@token_required
def api_declaration_previews():
    try:
        return jsonify(declaration_previews(g.current_player))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_declaration_previews failed')
        return jsonify({'error': '预读取检视候选时发生异常，请稍后重试。'}), 500


@main_bp.post('/api/game/declaration-preview')
@token_required
def api_declaration_preview():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(declaration_preview(
            g.current_player,
            str(payload.get('card_instance_id', '')),
            str(payload.get('location_id', '')),
            str(payload.get('selected_target_instance_id', '')),
        ))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_declaration_preview failed')
        return jsonify({'error': '读取检视候选时发生异常，请稍后重试。'}), 500


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
    payload = request.get_json(silent=True) or {}
    declaration_choices = payload.get('declaration_choices')
    if declaration_choices is not None and not isinstance(declaration_choices, list):
        declaration_choices = []
    planning_actions = payload.get('planning_actions')
    if planning_actions is not None and not isinstance(planning_actions, list):
        planning_actions = []
    try:
        return jsonify(end_turn(g.current_player, declaration_choices, planning_actions))
    except AppError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        logger.exception('api_end_turn failed')
        return jsonify({'error': '完成部署时发生异常，请稍后重试。'}), 500


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
