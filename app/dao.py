import json
from datetime import datetime, timedelta
from secrets import token_hex
from typing import Any

from peewee import DoesNotExist

from app.config import TOKEN_TTL_HOURS
from app.errors import RuleValidationError
from app.models import AccessToken, DeckBuild, GameRun, LoginCode, Player, PlayerTutorial, Room, RoomMember
from app.utils.logger import get_logger

logger = get_logger('nte.dao')
PERMANENT_PASSWORD_EXPIRES_AT = datetime(2999, 12, 31, 23, 59, 59)
MAX_NICKNAME_LENGTH = 8
MAX_PASSWORD_LENGTH = 16
ROOM_OPEN_STATUSES = frozenset({'waiting', 'ready', 'playing'})
ROOM_VISIBLE_STATUSES = ROOM_OPEN_STATUSES | frozenset({'victory', 'defeat', 'draw'})
TUTORIAL_SCOPES = frozenset({'home', 'build', 'table'})


def normalize_nickname(nickname: str) -> str:
    return (nickname or '').strip()[:MAX_NICKNAME_LENGTH]


def validate_password(password: str) -> str:
    password = (password or '').strip()
    if not password:
        raise RuleValidationError('密码不能为空。')
    if len(password) > MAX_PASSWORD_LENGTH:
        raise RuleValidationError(f'密码长度不能超过 {MAX_PASSWORD_LENGTH} 个字符。')
    return password


def normalize_tutorial_scope(scope: str) -> str:
    scope = (scope or '').strip().lower()
    if scope not in TUTORIAL_SCOPES:
        raise RuleValidationError('未知的教学手册。')
    return scope


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


def is_tutorial_completed(player: Player, scope: str) -> bool:
    scope = normalize_tutorial_scope(scope)
    record = PlayerTutorial.select().where(
        (PlayerTutorial.player == player) &
        (PlayerTutorial.scope == scope)
    ).first()
    return bool(record and record.completed)


def mark_tutorial_completed(player: Player, scope: str) -> PlayerTutorial:
    scope = normalize_tutorial_scope(scope)
    record, _ = PlayerTutorial.get_or_create(player=player, scope=scope)
    record.completed = True
    record.updated_at = datetime.utcnow()
    record.save()
    logger.info('mark_tutorial_completed player_uid=%s scope=%s', player.player_uid, scope)
    return record


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
        return None, '玩家未注册，请先向机器人发送注册账号指令。'
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
    record = AccessToken.select(AccessToken, Player).join(Player).where(
        (AccessToken.token == token) &
        (AccessToken.revoked == False) &
        (AccessToken.expires_at >= datetime.utcnow())
    ).first()
    if record is None:
        return None
    return record.player


def upsert_build(player: Player, character_id: str, item_ids: list[str] | dict[str, Any]) -> DeckBuild:
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
    raw_payload = json.loads(build.item_ids)
    if isinstance(raw_payload, list):
        payload: dict[str, Any] = {'item_ids': raw_payload}
    elif isinstance(raw_payload, dict):
        payload = raw_payload
    else:
        payload = {'item_ids': []}
    return {
        'character_id': build.character_id,
        **payload,
        'updated_at': build.updated_at.isoformat(),
    }


def _generate_room_code() -> str:
    while True:
        room_code = token_hex(3).upper()
        if not Room.select().where(Room.room_code == room_code).exists():
            return room_code


def serialize_room_member(member: RoomMember) -> dict[str, Any]:
    return {
        'player_uid': member.player.player_uid,
        'nickname': member.player.nickname or member.player.player_uid,
        'seat': member.seat,
        'is_host': member.is_host,
        'is_ready': member.is_ready,
        'joined_at': member.joined_at.isoformat(),
    }


def serialize_room(room: Room, members: list[RoomMember] | None = None) -> dict[str, Any]:
    payload = {
        'room_code': room.room_code,
        'mode': room.mode,
        'status': room.status,
        'host_player_uid': room.host.player_uid,
        'created_at': room.created_at.isoformat(),
        'updated_at': room.updated_at.isoformat(),
    }
    if members is not None:
        payload['members'] = [serialize_room_member(member) for member in members]
    return payload


def create_room(host: Player, mode: str) -> Room:
    room = Room.create(
        room_code=_generate_room_code(),
        mode=mode,
        status='waiting',
        host=host,
    )
    logger.info('create_room host_uid=%s room_code=%s mode=%s', host.player_uid, room.room_code, mode)
    return room


def get_room_by_code(room_code: str) -> Room | None:
    try:
        return Room.get(Room.room_code == room_code.upper())
    except DoesNotExist:
        return None


def get_room_member(room: Room, player: Player) -> RoomMember | None:
    return RoomMember.select().where(
        (RoomMember.room == room) &
        (RoomMember.player == player)
    ).first()


def list_room_members(room: Room) -> list[RoomMember]:
    return list(RoomMember.select().where(RoomMember.room == room).order_by(RoomMember.joined_at.asc()))


def get_current_room(player: Player, statuses: set[str] | frozenset[str] | None = None) -> Room | None:
    target_statuses = statuses or ROOM_VISIBLE_STATUSES
    member = (RoomMember
        .select(RoomMember, Room)
        .join(Room)
        .where(
            (RoomMember.player == player) &
            (Room.status.in_(target_statuses))
        )
        .order_by(Room.updated_at.desc())
        .first())
    if member is None:
        return None
    return member.room


def add_room_member(
    room: Room,
    player: Player,
    *,
    seat: str,
    is_host: bool,
    is_ready: bool,
) -> RoomMember:
    member, _ = RoomMember.get_or_create(room=room, player=player)
    member.seat = seat
    member.is_host = is_host
    member.is_ready = is_ready
    member.updated_at = datetime.utcnow()
    member.save()
    room.updated_at = datetime.utcnow()
    room.save()
    logger.info(
        'add_room_member room_code=%s player_uid=%s seat=%s is_host=%s is_ready=%s',
        room.room_code,
        player.player_uid,
        seat,
        is_host,
        is_ready,
    )
    return member


def set_room_member_ready(room: Room, player: Player, is_ready: bool) -> RoomMember:
    member = get_room_member(room, player)
    if member is None:
        raise RuleValidationError('当前玩家不在该房间中。')
    member.is_ready = is_ready
    member.updated_at = datetime.utcnow()
    member.save()
    room.updated_at = datetime.utcnow()
    room.save()
    logger.info('set_room_member_ready room_code=%s player_uid=%s is_ready=%s', room.room_code, player.player_uid, is_ready)
    return member


def update_room_status(room: Room, status: str) -> Room:
    room.status = status
    room.updated_at = datetime.utcnow()
    room.save(only=[Room.status, Room.updated_at])
    logger.info('update_room_status room_code=%s status=%s', room.room_code, status)
    return room


def upsert_run(room: Room, map_id: str, status: str, snapshot: dict[str, Any], *, touch_room: bool = True) -> GameRun:
    run, _ = GameRun.get_or_create(room=room)
    run.map_id = map_id
    run.status = status
    run.snapshot = json.dumps(snapshot, ensure_ascii=False)
    run.updated_at = datetime.utcnow()
    run.save(only=[GameRun.map_id, GameRun.status, GameRun.snapshot, GameRun.updated_at])
    if touch_room:
        room.updated_at = datetime.utcnow()
        room.save(only=[Room.updated_at])
    logger.info('upsert_run room_code=%s status=%s map_id=%s', room.room_code, status, map_id)
    return run


def get_run(room: Room) -> dict[str, Any] | None:
    run = GameRun.select().where(GameRun.room == room).first()
    if run is None:
        return None
    return {
        'status': run.status,
        'map_id': run.map_id,
        'snapshot': json.loads(run.snapshot or '{}'),
        'updated_at': run.updated_at.isoformat(),
    }


def clear_run(room: Room) -> None:
    logger.info('clear_run room_code=%s', room.room_code)
    GameRun.delete().where(GameRun.room == room).execute()


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
