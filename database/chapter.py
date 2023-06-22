from sys import maxsize

from database.data import Chapter
from database.sqlite import commit, fetchall, sqlescape

_TABLE = 'chapter'
_COLUMN_CID = 'cid'
_COLUMN_VID = 'vid'
_COLUMN_TRIGGER = 'trigger'  # uid.
_COLUMN_SLICER = 'slicer'
_COLUMN_STYLE = 'style'
_COLUMN_START = 'start'  # in seconds.
_COLUMN_LANG = 'lang'  # language code.
_COLUMN_CHAPTER = 'chapter'
_COLUMN_SUMMARY = 'summary'
_COLUMN_REFINED = 'refined'
_COLUMN_CREATE_TIMESTAMP = 'create_timestamp'
_COLUMN_UPDATE_TIMESTAMP = 'update_timestamp'


def create_chapter_table():
    commit(f'''
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            {_COLUMN_CID}     TEXT NOT NULL PRIMARY KEY,
            {_COLUMN_VID}     TEXT NOT NULL DEFAULT '',
            {_COLUMN_TRIGGER} TEXT NOT NULL DEFAULT '',
            {_COLUMN_SLICER}  TEXT NOT NULL DEFAULT '',
            {_COLUMN_STYLE}   TEXT NOT NULL DEFAULT '',
            {_COLUMN_START}   INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_LANG}    TEXT NOT NULL DEFAULT '',
            {_COLUMN_CHAPTER} TEXT NOT NULL DEFAULT '',
            {_COLUMN_SUMMARY} TEXT NOT NULL DEFAULT '',
            {_COLUMN_REFINED} INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_CREATE_TIMESTAMP} INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_UPDATE_TIMESTAMP} INTEGER NOT NULL DEFAULT 0
        )
        ''')
    commit(f'''
        CREATE INDEX IF NOT EXISTS idx_{_COLUMN_TRIGGER}
        ON {_TABLE} ({_COLUMN_TRIGGER})
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


def find_chapters_by_vid(vid: str, limit: int = maxsize) -> list[Chapter]:
    res = fetchall(f'''
        SELECT
              {_COLUMN_CID},
              {_COLUMN_VID},
              {_COLUMN_TRIGGER},
              {_COLUMN_SLICER},
              {_COLUMN_STYLE},
              {_COLUMN_START},
              {_COLUMN_LANG},
              {_COLUMN_CHAPTER},
              {_COLUMN_SUMMARY},
              {_COLUMN_REFINED}
         FROM {_TABLE}
        WHERE {_COLUMN_VID} = '{sqlescape(vid)}'
        ORDER BY {_COLUMN_START} ASC
        LIMIT {limit}
        ''')
    return list(map(lambda r: Chapter(
        cid=r[0],
        vid=r[1],
        trigger=r[2],
        slicer=r[3],
        style=r[4],
        start=r[5],
        lang=r[6],
        chapter=r[7],
        summary=r[8],
        refined=r[9],
    ), res))


def insert_chapters(chapters: list[Chapter]):
    for c in chapters:
        _insert_chapter(c)


def _insert_chapter(chapter: Chapter):
    commit(f'''
        INSERT INTO {_TABLE} (
            {_COLUMN_CID},
            {_COLUMN_VID},
            {_COLUMN_TRIGGER},
            {_COLUMN_SLICER},
            {_COLUMN_STYLE},
            {_COLUMN_START},
            {_COLUMN_LANG},
            {_COLUMN_CHAPTER},
            {_COLUMN_SUMMARY},
            {_COLUMN_REFINED},
            {_COLUMN_CREATE_TIMESTAMP},
            {_COLUMN_UPDATE_TIMESTAMP}
        ) VALUES (
            '{sqlescape(chapter.cid)}',
            '{sqlescape(chapter.vid)}',
            '{sqlescape(chapter.trigger)}',
            '{sqlescape(chapter.slicer)}',
            '{sqlescape(chapter.style)}',
             {chapter.start},
            '{sqlescape(chapter.lang)}',
            '{sqlescape(chapter.chapter)}',
            '{sqlescape(chapter.summary)}',
             {chapter.refined},
             STRFTIME('%s', 'NOW'),
             STRFTIME('%s', 'NOW')
        )
        ''')


def delete_chapters_by_vid(vid: str):
    commit(f'''
        DELETE FROM {_TABLE}
        WHERE {_COLUMN_VID} = '{sqlescape(vid)}'
        ''')
