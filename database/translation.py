from typing import Optional

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


def find_translation(vid: str, cid: str, lang: str) -> Optional[Translation]:
    res = fetchall(f'''
        SELECT
              {_COLUMN_VID},
              {_COLUMN_CID},
              {_COLUMN_LANG},
              {_COLUMN_CHAPTER},
              {_COLUMN_SUMMARY}
         FROM {_TABLE}
        WHERE {_COLUMN_VID}  = '{sqlescape(vid)}'
          AND {_COLUMN_CID}  = '{sqlescape(cid)}'
          AND {_COLUMN_LANG} = '{sqlescape(lang)}'
        LIMIT 1
        ''')

    if not res:
        return None

    res = res[0]
    return Translation(
        vid=res[0],
        cid=res[1],
        lang=res[2],
        chapter=res[3],
        summary=res[4],
    )


def insert_or_update_translation(translation: Translation):
    previous = find_translation(
        vid=translation.vid,
        cid=translation.cid,
        lang=translation.lang,
    )
    if not previous:
        commit(f'''
            INSERT INTO {_TABLE} (
                {_COLUMN_VID},
                {_COLUMN_CID},
                {_COLUMN_LANG},
                {_COLUMN_CHAPTER},
                {_COLUMN_SUMMARY},
                {_COLUMN_CREATE_TIMESTAMP},
                {_COLUMN_UPDATE_TIMESTAMP}
            ) VALUES (
                '{sqlescape(translation.vid)}',
                '{sqlescape(translation.cid)}',
                '{sqlescape(translation.lang)}',
                '{sqlescape(translation.chapter)}',
                '{sqlescape(translation.summary)}',
                STRFTIME('%s', 'NOW'),
                STRFTIME('%s', 'NOW')
            )
            ''')
    else:
        commit(f'''
            UPDATE {_TABLE}
               SET {_COLUMN_CHAPTER} = '{sqlescape(translation.chapter)}',
                   {_COLUMN_SUMMARY} = '{sqlescape(translation.summary)}',
                   {_COLUMN_UPDATE_TIMESTAMP} = STRFTIME('%s', 'NOW')
             WHERE {_COLUMN_VID}  = '{sqlescape(translation.vid)}'
               AND {_COLUMN_CID}  = '{sqlescape(translation.cid)}'
               AND {_COLUMN_LANG} = '{sqlescape(translation.lang)}'
            ''')


def delete_translation(vid: str):
    commit(f'''
        DELETE FROM {_TABLE}
        WHERE {_COLUMN_VID} = '{sqlescape(vid)}'
        ''')
