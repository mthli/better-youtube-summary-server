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


# TOOD
