from typing import Optional

from database.data import Feedback
from database.sqlite import commit, fetchall, sqlescape

_TABLE = 'feedback'
_COLUMN_VID = 'vid'
_COLUMN_GOOD = 'good'
_COLUMN_BAD = 'bad'
_COLUMN_CREATE_TIMESTAMP = 'create_timestamp'
_COLUMN_UPDATE_TIMESTAMP = 'update_timestamp'


def create_feedback_table():
    commit(f'''
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            {_COLUMN_VID}  TEXT NOT NULL PRIMARY KEY,
            {_COLUMN_GOOD} INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_BAD}  INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_CREATE_TIMESTAMP} INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_UPDATE_TIMESTAMP} INTEGER NOT NULL DEFAULT 0
        )
        ''')


def find_feedback(vid: str) -> Optional[Feedback]:
    res = fetchall(f'''
        SELECT
              {_COLUMN_VID},
              {_COLUMN_GOOD},
              {_COLUMN_BAD}
         FROM {_TABLE}
        WHERE {_COLUMN_VID} = '{sqlescape(vid)}'
        LIMIT 1
        ''')

    if not res:
        return None

    res = res[0]
    return Feedback(
        vid=res[0],
        good=res[1],
        bad=res[2],
    )


def delete_feedback(vid: str):
    commit(f'''
        DELETE FROM {_TABLE}
        WHERE {_COLUMN_VID} = '{sqlescape(vid)}'
        ''')
