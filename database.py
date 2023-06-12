from dataclasses import dataclass
from typing import Optional

from sqlite import commit, fetchall, sqlescape


@dataclass
class Chapter:
    cid: str = ''        # required.
    vid: str = ''        # required.
    timestamp: str = ''  # required.
    seconds: int = 0     # required.
    chapter: str = ''    # required.
    summary: str = ''    # optional.


_TABLE = 'chapter'
_COLUMN_VID = 'vid'
_COLUMN_CID = 'cid'
_COLUMN_TIMESTAMP = 'timestamp'  # HH:mm:ss
_COLUMN_SECONDS = 'seconds'
_COLUMN_CHAPTER = 'chapter'
_COLUMN_SUMMARY = 'summary'
_COLUMN_CREATE_TIMESTAMP = 'create_timestamp'
_COLUMN_UPDATE_TIMESTAMP = 'update_timestamp'


def create_chapter_table():
    commit(f'''
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            {_COLUMN_CID}       TEXT NOT NULL PRIMARY KEY,
            {_COLUMN_VID}       TEXT NOT NULL DEFAULT '',
            {_COLUMN_TIMESTAMP} TEXT NOT NULL DEFAULT '',
            {_COLUMN_SECONDS}   INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_CHAPTER}   TEXT NOT NULL DEFAULT '',
            {_COLUMN_SUMMARY}   TEXT NOT NULL DEFAULT '',
            {_COLUMN_CREATE_TIMESTAMP} INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_UPDATE_TIMESTAMP} INTEGER NOT NULL DEFAULT 0
        )
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_VID}
        ON {_TABLE} ({_COLUMN_VID})
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_CREATE_TIMESTAMP}
        ON {_TABLE} ({_COLUMN_CREATE_TIMESTAMP})
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_UPDATE_TIMESTAMP}
        ON {_TABLE} ({_COLUMN_UPDATE_TIMESTAMP})
        ''')
