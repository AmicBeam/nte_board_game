import json
from datetime import datetime, timedelta
from secrets import token_hex
from typing import Any

from peewee import DoesNotExist

from app.config import TOKEN_TTL_HOURS
from app.errors import RuleValidationError
from app.models import AccessToken, DeckBuild, GameRun, LoginCode, Player
from app.utils.logger import get_logger

logger = get_logger('nte.dao')
PERMANENT_PASSWORD_EXPIRES_AT = datetime(2999, 12, 31, 23, 59, 59)
MAX_NICKNAME_LENGTH = 8
MAX_PASSWORD_LENGTH = 16


def normalize_nickname(nickname: str) -> str:
    return (nickname or '').strip()[:MAX_NICKNAME_LENGTH]


def validate_password(password: str) -> str:
    password = (password or '').strip()
    if not password:
        raise RuleValidationError('密码不能为空。')
    if len(password) > MAX_PASSWORD_LENGTH:
        raise RuleValidationError(f'密码长度不能超过 {MAX_PASSWORD_LENGTH} 个字符。')
    return password


def get_or_create_player(player_uid: str, nickname: str = '') -> tuple[Player, bool]:
    nickname = normalize_nickname(nickname)
    player, created = Player.get_or_create(player_uid=player_uid, defaults={'nickname': nickname})
    if nickname and player.nickname != nickname:
        player.nickname = nickname
        player.updated_at = datetime.utcnow()
        player.save()
    logger.info('get_or_create_player uid=%s created=%s', player_uid, created)
    return player, created


def get_player_by_uid(player_uid: str) -> Player | None:
    try:
        return Player.get(Player.player_uid == player_uid)
    except DoesNotExist:
        return None


def create_login_code(player: Player, code: str) -> LoginCode:
    code = validate_password(code)
    LoginCode.update(used=True).where(
        (LoginCode.player == player) &
        (LoginCode.used == False) &
        (LoginCode.purpose == 'web_login')
    ).execute()
    record = LoginCode.create(
        player=player,
        code=code,
        purpose='web_login',
        used=False,
        expires_at=PERMANENT_PASSWORD_EXPIRES_AT,
    )
    logger.info('create_login_code player_uid=%s', player.player_uid)
    return record


def verify_login_code(player_uid: str, code: str) -> tuple[Player | None, str | None]:
    player = get_player_by_uid(player_uid)
    if player is None:
        return None, '玩家未注册，请先向机器人发送注册账户指令。'
    login_code = LoginCode.select().where(
        (LoginCode.player == player) &
        (LoginCode.code == code) &
        (LoginCode.used == False)
    ).order_by(LoginCode.created_at.desc()).first()
    if login_code is None:
        return None, '密码错误。'
    logger.info('verify_login_code success player_uid=%s', player_uid)
    return player, None


def create_access_token(player: Player) -> AccessToken:
    token = token_hex(24)
    record = AccessToken.create(
        player=player,
        token=token,
        revoked=False,
        expires_at=datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS),
    )
    logger.info('create_access_token player_uid=%s', player.player_uid)
    return record


def get_player_by_token(token: str) -> Player | None:
    if not token:
        return None
    record = AccessToken.select().where(
        (AccessToken.token == token) &
        (AccessToken.revoked == False) &
        (AccessToken.expires_at >= datetime.utcnow())
    ).first()
    if record is None:
        return None
    return record.player


def upsert_build(player: Player, character_id: str, item_ids: list[str]) -> DeckBuild:
    payload = json.dumps(item_ids, ensure_ascii=False)
    build, _ = DeckBuild.get_or_create(player=player)
    build.character_id = character_id
    build.item_ids = payload
    build.updated_at = datetime.utcnow()
    build.save()
    logger.info('upsert_build player_uid=%s character_id=%s item_count=%s', player.player_uid, character_id, len(item_ids))
    return build


def get_build(player: Player) -> dict[str, Any] | None:
    build = DeckBuild.select().where(DeckBuild.player == player).first()
    if build is None:
        return None
    return {
        'character_id': build.character_id,
        'item_ids': json.loads(build.item_ids),
        'updated_at': build.updated_at.isoformat(),
    }


def upsert_run(player: Player, map_id: str, status: str, snapshot: dict[str, Any]) -> GameRun:
    run, _ = GameRun.get_or_create(player=player)
    run.map_id = map_id
    run.status = status
    run.snapshot = json.dumps(snapshot, ensure_ascii=False)
    run.updated_at = datetime.utcnow()
    run.save()
    logger.info('upsert_run player_uid=%s status=%s map_id=%s', player.player_uid, status, map_id)
    return run


def get_run(player: Player) -> dict[str, Any] | None:
    run = GameRun.select().where(GameRun.player == player).first()
    if run is None:
        return None
    return {
        'status': run.status,
        'map_id': run.map_id,
        'snapshot': json.loads(run.snapshot or '{}'),
        'updated_at': run.updated_at.isoformat(),
    }


def clear_run(player: Player) -> None:
    logger.info('clear_run player_uid=%s', player.player_uid)
    GameRun.delete().where(GameRun.player == player).execute()


def issue_mock_login(player_uid: str, nickname: str, code: str) -> Player:
    player, _ = get_or_create_player(player_uid, nickname)
    create_login_code(player, code)
    return player


def update_player_nickname(player: Player, nickname: str) -> Player:
    nickname = normalize_nickname(nickname)
    if not nickname:
        raise RuleValidationError('用户名不能为空。')
    player.nickname = nickname
    player.updated_at = datetime.utcnow()
    player.save()
    logger.info('update_player_nickname player_uid=%s nickname=%s', player.player_uid, nickname)
    return player


def update_player_password(player: Player, password: str) -> None:
    create_login_code(player, password)
    logger.info('update_player_password player_uid=%s', player.player_uid)
