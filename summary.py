import json

from dataclasses import dataclass

from bs4 import BeautifulSoup
from flask import abort
from logger import logger
from openai import Role, TokenLimit, \
    build_message, \
    chat, \
    count_tokens, \
    get_content


@dataclass
class Chapter:
    timestamp: str = 0  # required.
    seconds: int = 0    # required.
    chapter: str = ''   # required.
    summary: str = ''   # optional.


@dataclass
class TimedText:
    start: float = 0  # seconds; required.
    dur: float = 0    # seconds; required.
    text: str = ''    # required.


_DETECT_CHAPTERS_TOKEN_LIMIT = TokenLimit.GPT_3_5_TURBO.value - 160  # nopep8, 3936.
_DETECT_CHAPTERS_PROMPT = '''
Given the following content, trying to detect its chapter.
The content is taken from a video, possibly a conversation but without role markers.

The content consists of many sentences,
the sentences format is `[index] [start time in seconds] [text...]`,
for example `[0] [10] [How are you]`.

Your job is trying to detect the content chapter from top to bottom,
the chapter should contains as much sentences as possible from top to bottom,
and you can take the first obvious context as the chapter.

Return a JSON object containing the following fields:
- "chapter": string field, the concise title of chapter in a few words.
- "seconds": int field, the [start time] of the chapter in seconds, must >= {start_time}.
- "timestamp": string field, the [start time] of the chapter in "HH:mm:ss" format.
- "end_at": int field, the chapter context end at which [index].

Do not output any redundant explanation or information other than JSON.

> Content:
>>>
{content}
>>>

> JSON:
'''


async def summarize(vid: str, timedtext: str, chapters: list[dict] = [], lang: str = 'en'):
    timed_texts = _parse_timed_texts(vid, timedtext)

    chapters: list[Chapter] = _parse_chapters(vid, chapters)
    if not chapters:
        chapters = await _detect_chapters(vid, timed_texts)
        if not chapters:
            abort(500, f'summarize failed, no chapters, vid={vid}')

    # TODO


def _parse_timed_texts(vid: str, src: str) -> list[TimedText]:
    timed_texts: list[TimedText] = []
    soup = BeautifulSoup(src, 'lxml')

    transcript_el = soup.find('transcript')
    if not transcript_el:
        abort(404, f'transcript not found, vid={vid}')

    text_els = transcript_el.find_all('text')
    if not text_els:
        abort(404, f'transcript is empty, vid={vid}')

    for text_el in text_els:
        timed_texts.append(TimedText(
            start=float(text_el.attrs['start']),
            dur=float(text_el.attrs['dur']),
            text=text_el.text,
        ))

    if not timed_texts:
        abort(400, f'transcript format invalid, vid={vid}')

    return timed_texts


def _parse_chapters(vid: str, chapters: list[dict]) -> list[Chapter]:
    res: list[Chapter] = []

    if not chapters:
        logger.info(f'parse chapters, but chapters is empty, vid={vid}')
        return res

    try:
        for c in chapters:
            timestamp: str = c['timestamp']

            seconds: int = 0
            array: list[str] = timestamp.split(':')
            if len(array) == 2:
                seconds = int(array[0]) * 60 + int(array[1])
            elif len(array) == 3:
                seconds = int(array[0]) * 60 * 60 + int(array[1]) * 60 + int(array[2])  # nopep8.

            res.append(Chapter(
                timestamp=timestamp,
                seconds=seconds,
                chapter=c['title'],
            ))
    except Exception:
        logger.exception(f'parse chapters failed, vid={vid}')
        return res

    return res


async def _detect_chapters(vid: str, timed_texts: list[TimedText]) -> list[Chapter]:
    chapters: list[Chapter] = []
    timed_texts_start = 0
    latest_end_at = -1

    while True:
        texts = timed_texts[timed_texts_start:]
        if not texts:
            break  # drained.

        content = ''
        start_time = int(texts[0].start)

        for t in texts:
            temp = f'[{timed_texts_start}] [{int(t.start)}] [{t.text}]'
            temp = content + '\n' + temp if content else temp
            prompt = _DETECT_CHAPTERS_PROMPT.format(
                content=temp,
                start_time=start_time,
            )

            message = build_message(Role.USER, prompt)
            if count_tokens([message]) < _DETECT_CHAPTERS_TOKEN_LIMIT:
                content = temp.strip()
                timed_texts_start += 1
            else:
                break  # for.

        prompt = _DETECT_CHAPTERS_PROMPT.format(
            content=content,
            start_time=start_time,
        )

        message = build_message(Role.USER, prompt)
        body = await chat(messages=[message], top_p=0.1, timeout=120)
        content = get_content(body)
        logger.info(f'detect chapters, vid={vid}, content=\n{content}')

        res: dict = json.loads(content)
        timestamp = res.get('timestamp', '').strip()
        chapter = res.get('chapter', '').strip()
        seconds = res.get('seconds', -1)
        end_at = res.get('end_at')

        # Looks like it's the end and meanless, so ignore the chapter.
        if type(end_at) is not int:  # NoneType.
            break  # drained.

        if timestamp and chapter and seconds >= 0:
            chapters.append(Chapter(
                timestamp=timestamp,
                seconds=seconds,
                chapter=chapter,
            ))

        # Looks like it's the end.
        # if type(end_at) is not int:  # NoneType.
        #     break  # drained.

        if end_at <= latest_end_at:
            logger.warning(f'detect chapters, avoid infinite loop, vid={vid}')
            latest_end_at += 5  # force a different context.
            timed_texts_start = latest_end_at
        else:
            latest_end_at = end_at
            timed_texts_start = end_at + 1

    return chapters
