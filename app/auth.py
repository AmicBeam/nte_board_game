from functools import wraps
from collections.abc import Callable
from typing import Any

from flask import g, jsonify, request

from app.dao import create_access_token, get_player_by_token, verify_login_code
from app.db import atomic_transaction
from app.utils.logger import get_logger

logger = get_logger('nte.auth')


def login_with_code(player_uid: str, code: str) -> tuple[dict[str, Any] | None, str | None]:
    with atomic_transaction():
        player, error = verify_login_code(player_uid, code)
        if error:
            logger.warning('login_with_code failed player_uid=%s error=%s', player_uid, error)
            return None, error
        token_record = create_access_token(player)
    logger.info('login_with_code success player_uid=%s', player_uid)
    return {
        'token': token_record.token,
        'player': {
            'player_uid': player.player_uid,
            'nickname': player.nickname or player.player_uid,
        },
    }, None


def token_required(view_func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view_func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        header = request.headers.get('Authorization', '')
        token = header.replace('Bearer ', '', 1).strip() if header.startswith('Bearer ') else ''
        player = get_player_by_token(token)
        if player is None:
            logger.warning('token_required rejected request path=%s', request.path)
            return jsonify({'error': '未登录或 token 已失效。'}), 401
        g.current_player = player
        return view_func(*args, **kwargs)
    return wrapped
