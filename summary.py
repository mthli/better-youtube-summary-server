import asyncio
import json

from dataclasses import dataclass, asdict
from sys import maxsize
from uuid import uuid4

from bs4 import BeautifulSoup
from flask import abort
from flask_sse import sse
from logger import logger
from openai import Role, TokenLimit, \
    build_message, \
    chat, \
    count_tokens, \
    get_content


@dataclass
class Chapter:
    vid: str = ''        # required.
    cid: str = ''        # required.
    timestamp: str = ''  # required.
    seconds: int = 0     # required.
    chapter: str = ''    # required.
    summary: str = ''    # optional.


@dataclass
class TimedText:
    start: float = 0  # required; in seconds.
    dur: float = 0    # required; in seconds.
    text: str = ''    # required.


_SSE_TYPE_CHAPTER = 'chapter'
_SSE_TYPE_CHAPTERS = 'chapters'
_SSE_TYPE_CLOSE = 'close'

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

# https://github.com/hwchase17/langchain/blob/master/langchain/chains/summarize/refine_prompts.py#L21
_SUMMARIZE_FIRST_CHAPTER_TOKEN_LIMIT = TokenLimit.GPT_3_5_TURBO.value * 7 / 8  # nopep8, 3584.
_SUMMARIZE_FIRST_CHAPTER_PROMPT = '''
List the most important points of the following content.
The content is taken from a video, possibly a conversation but without role markers.

If a context is not important or doesn't make sense, don't include it to the output.
Do not output redundant points, keep the output concise.
Do not output any redundant explanation or information.

> Content, and the chapter is about "{chapter}":
>>>
{content}
>>>

> CONCISE BULLET LIST SUMMARY:
'''

# https://github.com/hwchase17/langchain/blob/master/langchain/chains/summarize/refine_prompts.py#L4
_SUMMARIZE_NEXT_CHAPTER_TOKEN_LIMIT = TokenLimit.GPT_3_5_TURBO.value * 5 / 8  # nopep8, 2560.
_SUMMARIZE_NEXT_CHAPTER_PROMPT = '''
Your job is to produce a final bullet list summary.

We have provided an existing bullet list summary up to a certain point.
We have the opportunity to refine the existing summary (only if needed) with some more content below.
The content are taken from a video, possibly a conversation but without role markers.

Refine the existing bullet list summary (only if needed) with the given content.
Do not refine the existing summary with the given content if it isn't useful or doesn't make sense.
Do not output redundant points, keep the output concise.
Do not output any redundant explanation or information.

If the existing bullet list summary is too long, you can summarize it again, keep the important points.

> Existing bullet list summary, and the chapter is about "{chapter}":
>>>
{summary}
>>>

> More content, and the chapter is about "{chapter}":
>>>
{content}
>>>

> REFINE BULLET LIST SUMMARY:
'''


async def summarize(vid: str, timedtext: str, chapters: list[dict] = []) -> list[Chapter]:
    timed_texts = _parse_timed_texts(vid, timedtext)

    chapters: list[Chapter] = _parse_chapters(vid, chapters)
    if not chapters:
        chapters = await _detect_chapters(vid, timed_texts)
        if not chapters:
            abort(500, f'summarize failed, no chapters, vid={vid}')
    else:
        data = list(map(lambda c: asdict(c), chapters))
        sse.publish(data, type=_SSE_TYPE_CHAPTERS, channel=vid)

    tasks = []
    for i, c in enumerate(chapters):
        start_time = c.seconds
        end_time = chapters[i + 1].seconds if i + 1 < len(chapters) else maxsize  # nopep8.
        texts = _get_timed_texts_in_range(
            timed_texts=timed_texts,
            start_time=start_time,
            end_time=end_time,
        )
        tasks.append(_summarize_chapter(chapter=c, timed_texts=texts))

    # Map reduce tasks for faster processing.
    res = await asyncio.gather(*tasks, return_exceptions=True)
    for r in res:
        if isinstance(r, Exception):
            logger.error(f'summarize, but has exception, vid={vid}, e={r}')

    sse.publish({'vid': vid}, type=_SSE_TYPE_CLOSE, channel=vid)
    return chapters


def _parse_timed_texts(vid: str, src: str) -> list[TimedText]:
    timed_texts: list[TimedText] = []
    soup = BeautifulSoup(src, 'xml')

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
                vid=vid,
                cid=str(uuid4()),
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
        body = await chat(messages=[message], top_p=0.1, timeout=90)
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
            data = Chapter(
                vid=vid,
                cid=str(uuid4()),
                timestamp=timestamp,
                seconds=seconds,
                chapter=chapter,
            )
            chapters.append(data)
            sse.publish(asdict(data), type=_SSE_TYPE_CHAPTER, channel=vid)

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


def _get_timed_texts_in_range(timed_texts: list[TimedText], start_time: int, end_time: int = maxsize) -> list[TimedText]:
    res: list[TimedText] = []

    for t in timed_texts:
        if start_time <= t.start and t.start < end_time:
            res.append(t)

    return res


async def _summarize_chapter(chapter: Chapter, timed_texts: list[TimedText]):
    summary = ''
    summary_start = 0
    is_first_summarize = True

    while True:
        texts = timed_texts[summary_start:]
        if not texts:
            break  # drained.

        content = ''
        content_has_changed = False

        for t in texts:
            temp = content + '\n' + t.text if content else t.text
            if is_first_summarize:
                prompt = _SUMMARIZE_FIRST_CHAPTER_PROMPT.format(
                    chapter=chapter.chapter,
                    content=temp,
                )
            else:
                prompt = _SUMMARIZE_NEXT_CHAPTER_PROMPT.format(
                    chapter=chapter.chapter,
                    summary=summary,
                    content=temp,
                )

            message = build_message(Role.USER, prompt)
            token_limit = _SUMMARIZE_FIRST_CHAPTER_TOKEN_LIMIT \
                if is_first_summarize else _SUMMARIZE_NEXT_CHAPTER_TOKEN_LIMIT
            if count_tokens([message]) < token_limit:
                content_has_changed = True
                content = temp.strip()
                summary_start += 1
            else:
                break  # for.

        # FIXME (Matthew Lee) it is possible that content not changed, simply avoid redundant requests.
        if not content_has_changed:
            logger.warning(f'summarize chapter, but content not changed, vid={chapter.vid}')  # nopep8.
            break

        if is_first_summarize:
            prompt = _SUMMARIZE_FIRST_CHAPTER_PROMPT.format(
                chapter=chapter.chapter,
                content=content,
            )
        else:
            prompt = _SUMMARIZE_NEXT_CHAPTER_PROMPT.format(
                chapter=chapter.chapter,
                summary=summary,
                content=content,
            )

        message = build_message(Role.USER, prompt)
        body = await chat(messages=[message], top_p=0.1, timeout=90)
        summary = get_content(body).strip()

        logger.info(f'summarize chapter, '
                    f'vid={chapter.vid}, '
                    f'chapter={chapter}, '
                    f'is_first_summarize={is_first_summarize}, '
                    f'summary=\n{summary}')

        chapter.summary = summary  # cache even not finished.
        is_first_summarize = False

    chapter.summary = summary.strip()
    sse.publish(asdict(chapter), type=_SSE_TYPE_CHAPTER, channel=chapter.vid)
