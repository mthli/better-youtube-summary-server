from dataclasses import dataclass

from sqlite import commit, fetchall, sqlescape


@dataclass
class Chapter:
    cid: str = ''        # required.
    vid: str = ''        # required.
    seconds: int = 0     # required.
    lang: str = ''       # required; language code, empty means unknown.
    chapter: str = ''    # required.
    summary: str = ''    # optional.


_TABLE = 'chapter'
_COLUMN_CID = 'cid'
_COLUMN_VID = 'vid'
_COLUMN_SECONDS = 'seconds'
_COLUMN_LANG = 'lang'  # language code.
_COLUMN_CHAPTER = 'chapter'
_COLUMN_SUMMARY = 'summary'
_COLUMN_CREATE_TIMESTAMP = 'create_timestamp'
_COLUMN_UPDATE_TIMESTAMP = 'update_timestamp'


def create_chapter_table():
    commit(f'''
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            {_COLUMN_CID}      TEXT NOT NULL PRIMARY KEY,
            {_COLUMN_VID}      TEXT NOT NULL DEFAULT '',
            {_COLUMN_SECONDS}  INTEGER NOT NULL DEFAULT 0,
            {_COLUMN_LANG}     TEXT NOT NULL DEFAULT '',
            {_COLUMN_CHAPTER}  TEXT NOT NULL DEFAULT '',
            {_COLUMN_SUMMARY}  TEXT NOT NULL DEFAULT '',
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


def find_chapters_by_vid(vid: str) -> list[Chapter]:
    res = fetchall(f'''
        SELECT
              {_COLUMN_CID},
              {_COLUMN_VID},
              {_COLUMN_SECONDS},
              {_COLUMN_LANG},
              {_COLUMN_CHAPTER},
              {_COLUMN_SUMMARY}
         FROM {_TABLE}
        WHERE {_COLUMN_VID} = '{sqlescape(vid)}'
        ORDER BY {_COLUMN_SECONDS} ASC
        ''')
    return list(map(lambda r: Chapter(
        cid=r[0],
        vid=r[1],
        seconds=r[2],
        lang=r[3],
        chapter=r[4],
        summary=r[5],
    ), res))


def insert_chapters(chapters: list[Chapter]):
    for c in chapters:
        _insert_chapter(c)


def _insert_chapter(chapter: Chapter):
    commit(f'''
        INSERT INTO {_TABLE} (
            {_COLUMN_CID},
            {_COLUMN_VID},
            {_COLUMN_SECONDS},
            {_COLUMN_LANG},
            {_COLUMN_CHAPTER},
            {_COLUMN_SUMMARY},
            {_COLUMN_CREATE_TIMESTAMP},
            {_COLUMN_UPDATE_TIMESTAMP}
        ) VALUES (
            '{sqlescape(chapter.cid)}',
            '{sqlescape(chapter.vid)}',
             {chapter.seconds},
            '{sqlescape(chapter.lang)}',
            '{sqlescape(chapter.chapter)}',
            '{sqlescape(chapter.summary)}',
             STRFTIME('%s', 'NOW'),
             STRFTIME('%s', 'NOW')
        )
        ''')


def delete_chapters_by_vid(vid: str):
    commit(f'''
        DELETE FROM {_TABLE}
        WHERE {_COLUMN_VID} = '{sqlescape(vid)}'
        ''')
