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


class GameRun(BaseModel):
    id = AutoField()
    player = ForeignKeyField(Player, backref='runs', on_delete='CASCADE', unique=True)
    status = CharField(default='idle')
    map_id = CharField(default='')
    snapshot = TextField(default='{}')
    updated_at = DateTimeField(default=datetime.utcnow)
