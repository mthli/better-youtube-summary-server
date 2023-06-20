from sys import maxsize
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


def insert_or_update_feedback(feedback: Feedback):
    if feedback.good < 0:
        feedback.good = 0
    elif feedback.good >= maxsize:
        feedback.good = maxsize

    if feedback.bad < 0:
        feedback.bad = 0
    elif feedback.bad >= maxsize:
        feedback.bad = maxsize

    previous = find_feedback(feedback.vid)
    if not previous:
        commit(f'''
            INSERT INTO {_TABLE} (
                {_COLUMN_VID},
                {_COLUMN_GOOD},
                {_COLUMN_BAD},
                {_COLUMN_CREATE_TIMESTAMP},
                {_COLUMN_UPDATE_TIMESTAMP}
            ) VALUES (
                '{sqlescape(feedback.vid)}',
                 {feedback.good},
                 {feedback.bad},
                STRFTIME('%s', 'NOW'),
                STRFTIME('%s', 'NOW')
            )
            ''')
    else:
        commit(f'''
            UPDATE {_TABLE}
               SET {_COLUMN_GOOD} = {feedback.good},
                   {_COLUMN_BAD}  = {feedback.good},
                   {_COLUMN_UPDATE_TIMESTAMP} = STRFTIME('%s', 'NOW')
             WHERE {_COLUMN_VID}  = '{sqlescape(feedback.vid)}'
            ''')


def delete_feedback(vid: str):
    commit(f'''
        DELETE FROM {_TABLE}
        WHERE {_COLUMN_VID} = '{sqlescape(vid)}'
        ''')
