from database.data import Translation
from database.sqlite import commit, fetchall, sqlescape

_TABLE = 'translation'
_COLUMN_VID = 'vid'
_COLUMN_CID = 'cid'
_COLUMN_LANG = 'lang'
_COLUMN_CHAPTER = 'chapter'
_COLUMN_SUMMARY = 'summary'
_COLUMN_CREATE_TIMESTAMP = 'create_timestamp'
_COLUMN_UPDATE_TIMESTAMP = 'update_timestamp'


def create_translation_table():
    commit(f'''
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            {_COLUMN_VID}              TEXT NOT NULL DEFAULT '',
            {_COLUMN_CID}              TEXT NOT NULL DEFAULT '',
            {_COLUMN_LANG}             TEXT NOT NULL DEFAULT '',
            {_COLUMN_CHAPTER}          TEXT NOT NULL DEFAULT '',
            {_COLUMN_SUMMARY}          TEXT NOT NULL DEFAULT '',
            {_COLUMN_CREATE_TIMESTAMP} INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_UPDATE_TIMESTAMP} INTEGER NOT NULL DEFAULT 0
        )
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_VID}
        ON {_TABLE} ({_COLUMN_VID})
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_CID}
        ON {_TABLE} ({_COLUMN_CID})
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_LANG}
        ON {_TABLE} ({_COLUMN_LANG})
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_CREATE_TIMESTAMP}
        ON {_TABLE} ({_COLUMN_CREATE_TIMESTAMP})
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_UPDATE_TIMESTAMP}
        ON {_TABLE} ({_COLUMN_UPDATE_TIMESTAMP})
        ''')
