from datetime import datetime

from peewee import AutoField, BooleanField, CharField, DateTimeField, ForeignKeyField, IntegerField, Model, TextField

from app.db import db


class BaseModel(Model):
    class Meta:
        database = db


class Player(BaseModel):
    id = AutoField()
    player_uid = CharField(unique=True, max_length=64)
    nickname = CharField(default='')
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)


class PlayerTutorial(BaseModel):
    id = AutoField()
    player = ForeignKeyField(Player, backref='tutorials', on_delete='CASCADE')
    scope = CharField(max_length=32)
    completed = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        indexes = (
            (('player', 'scope'), True),
        )


class LoginCode(BaseModel):
    id = AutoField()
    player = ForeignKeyField(Player, backref='login_codes', on_delete='CASCADE')
    code = CharField(max_length=16)
    purpose = CharField(default='web_login')
    used = BooleanField(default=False)
    expires_at = DateTimeField()
    created_at = DateTimeField(default=datetime.utcnow)


class AccessToken(BaseModel):
    id = AutoField()
    player = ForeignKeyField(Player, backref='tokens', on_delete='CASCADE')
    token = CharField(unique=True, max_length=128)
    revoked = BooleanField(default=False)
    expires_at = DateTimeField()
    created_at = DateTimeField(default=datetime.utcnow)


class DeckBuild(BaseModel):
    id = AutoField()
    player = ForeignKeyField(Player, backref='builds', on_delete='CASCADE', unique=True)
    character_id = CharField(default='')
    item_ids = TextField(default='[]')
    updated_at = DateTimeField(default=datetime.utcnow)


class Room(BaseModel):
    id = AutoField()
    room_code = CharField(unique=True, max_length=12)
    mode = CharField(default='solo')
    status = CharField(default='waiting')
    host = ForeignKeyField(Player, backref='hosted_rooms', on_delete='CASCADE')
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)


class RoomMember(BaseModel):
    id = AutoField()
    room = ForeignKeyField(Room, backref='members', on_delete='CASCADE')
    player = ForeignKeyField(Player, backref='room_memberships', on_delete='CASCADE')
    seat = CharField(default='host')
    is_host = BooleanField(default=False)
    is_ready = BooleanField(default=False)
    joined_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        indexes = (
            (('room', 'player'), True),
        )


class GameRun(BaseModel):
    id = AutoField()
    room = ForeignKeyField(Room, backref='run', on_delete='CASCADE', unique=True)
    status = CharField(default='idle')
    map_id = CharField(default='')
    snapshot = TextField(default='{}')
    updated_at = DateTimeField(default=datetime.utcnow)
