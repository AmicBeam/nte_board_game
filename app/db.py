from contextlib import contextmanager
from collections.abc import Iterator

from peewee import Model, SqliteDatabase

from app.config import DATABASE_PATH

db = SqliteDatabase(DATABASE_PATH, pragmas={
    'foreign_keys': 1,
    'journal_mode': 'wal',
    'synchronous': 'normal',
    'busy_timeout': 5000,
})


def init_db(models: list[type[Model]]) -> None:
    if db.is_closed():
        db.connect(reuse_if_open=True)
    db.create_tables(models)


@contextmanager
def atomic_transaction() -> Iterator[object]:
    if db.is_closed():
        db.connect(reuse_if_open=True)
    with db.atomic() as txn:
        yield txn
