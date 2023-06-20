from typing import Optional

from database.data import User
from database.sqlite import commit, fetchall, sqlescape


_TABLE = 'user'
_COLUMN_UID = 'uid'
_COLUMN_IS_DELETED = 'is_deleted'
_COLUMN_CREATE_TIMESTAMP = 'create_timestamp'
_COLUMN_UPDATE_TIMESTAMP = 'update_timestamp'


def create_user_table():
    commit(f'''
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            {_COLUMN_UID}              TEXT NOT NULL PRIMARY KEY,
            {_COLUMN_IS_DELETED}       INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_CREATE_TIMESTAMP} INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_UPDATE_TIMESTAMP} INTEGER NOT NULL DEFAULT 0
        )
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_CREATE_TIMESTAMP}
        ON {_TABLE} ({_COLUMN_CREATE_TIMESTAMP})
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_UPDATE_TIMESTAMP}
        ON {_TABLE} ({_COLUMN_UPDATE_TIMESTAMP})
        ''')


def find_user(uid: str) -> Optional[User]:
    res = fetchall(f'''
        SELECT
              {_COLUMN_UID},
              {_COLUMN_IS_DELETED}
         FROM {_TABLE}
        WHERE {_COLUMN_UID} = '{sqlescape(uid)}'
        LIMIT 1
        ''')

    if not res:
        return None

    res = res[0]
    return User(
        uid=res[0],
        is_deleted=bool(res[1]),
    )


def insert_or_update_user(user: User):
    previous = find_user(user.uid)
    if not previous:
        commit(f'''
            INSERT INTO {_TABLE} (
                {_COLUMN_UID},
                {_COLUMN_IS_DELETED},
                {_COLUMN_CREATE_TIMESTAMP},
                {_COLUMN_UPDATE_TIMESTAMP}
            ) VALUES (
                '{sqlescape(user.uid)}',
                 {int(user.is_deleted)},
                STRFTIME('%s', 'NOW'),
                STRFTIME('%s', 'NOW')
            )
            ''')
    else:
        commit(f'''
            UPDATE {_TABLE}
               SET {_COLUMN_IS_DELETED} = {int(user.is_deleted)},
                   {_COLUMN_UPDATE_TIMESTAMP} = STRFTIME('%s', 'NOW')
             WHERE {_COLUMN_UID} = '{sqlescape(user.uid)}'
            ''')
