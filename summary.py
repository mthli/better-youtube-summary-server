import asyncio
import json

from sys import maxsize
from uuid import uuid4

from quart import abort
from youtube_transcript_api import YouTubeTranscriptApi

from database.data import Chapter, Slicer, SummaryState, TimedText, \
    build_summary_response
from logger import logger
from openai import Model, Role, TokenLimit, \
    build_message, \
    chat, \
    count_tokens, \
    get_content
from sse import SseEvent, sse_publish

# FIXME (Matthew Lee) how to use gpt-3.5-turbo-16k?
_GENERATE_CHAPTERS_TOKEN_LIMIT = TokenLimit.GPT_3_5_TURBO - 160  # nopep8, 3936.
_GENERATE_CHAPTERS_SYSTEM_PROMPT = '''
Given the following content, trying to generate its chapter.

The content is a piece of video subtitles represented as a JSON array,
the format of the JSON array elements is as follows:

```json
{{
  "index":   int field, the subtitle line index.
  "seconds": int field, the subtitle start time in seconds.
  "text": string field, the subtitle text itself.
}}
```

Your job is trying to generate the chapter of the content,
the chapter context should include most of subtitles from top to bottom,
and ignore irrelevant parts.

Return a JSON object containing the following fields:

```json
{{
  "chapter":   string field, give a concise title of the chapter context.
  "seconds":      int field, the start time of the chapter in seconds, must >= {start_time}.
  "timestamp": string field, the start time of the chapter in "HH:mm:ss" format.
  "end_at":       int field, the chapter context end at which line index.
}}
```

Do not output any redundant explanation or information other than JSON.
'''

# FIXME (Matthew Lee) how to use gpt-3.5-turbo-16k?
# https://github.com/hwchase17/langchain/blob/master/langchain/chains/summarize/refine_prompts.py#L21
_SUMMARIZE_FIRST_CHAPTER_TOKEN_LIMIT = TokenLimit.GPT_3_5_TURBO * 7 / 8  # nopep8, 3584.
_SUMMARIZE_FIRST_CHAPTER_SYSTEM_PROMPT = '''
List the most important points of the following content according to the topic of "{chapter}".
The content is a piece of video subtitles, consists of many lines.

Each bullet point should end with a period.

Do not output any redundant or irrelevant points, keep the output concise.
Do not output any redundant explanation or information.
'''

# FIXME (Matthew Lee) how to use gpt-3.5-turbo-16k?
# https://github.com/hwchase17/langchain/blob/master/langchain/chains/summarize/refine_prompts.py#L4
_SUMMARIZE_NEXT_CHAPTER_TOKEN_LIMIT = TokenLimit.GPT_3_5_TURBO * 5 / 8  # nopep8, 2560.
_SUMMARIZE_NEXT_CHAPTER_SYSTEM_PROMPT = '''
We have provided an existing bullet list summary up to a certain point,
and its topic is about "{chapter}",

```
{summary}
```

We have the opportunity to refine the existing summary (only if needed) with some more content.
The content is a piece of video subtitles, consists of many lines.

Refine the existing bullet list summary (only if needed) with the given content.
Each bullet point should end with a period.

Do not refine the existing summary with the given content if it isn't useful or doesn't make sense.
Do not output any redundant or irrelevant points, keep the output concise.
Do not output any redundant explanation or information.

If the existing bullet list summary is too long, you can summarize it again, keep the important points.
'''


# NoTranscriptFound, TranscriptsDisabled...
def parse_timed_texts_and_lang(vid: str) -> tuple[list[TimedText], str]:
    timed_texts: list[TimedText] = []

    # https://en.wikipedia.org/wiki/Languages_used_on_the_Internet#Content_languages_on_YouTube
    transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
    transcript = transcript_list.find_transcript([
        'en',  # English.
        'es',  # Spanish.
        'pt',  # Portuguese.
        'hi',  # Hindi.
        'ko',  # Korean.
        'zh-Hans',  # Chinese (Simplified).
        'zh-Hant',  # Chinese (Traditional).
        'ar',  # Arabic.
        'id',  # Indonesian.
        'fr',  # French.
        'ja',  # Japanese.
        'ru',  # Russian.
        'de',  # German.
    ])

    lang = transcript.language_code
    array: list[dict] = transcript.fetch()

    for d in array:
        timed_texts.append(TimedText(
            start=d['start'],
            duration=d['duration'],
            lang=lang,
            text=d['text'],
        ))

    return timed_texts, lang


async def summarize(
    vid: str,
    trigger: str,
    chapters: list[dict],
    timed_texts: list[TimedText],
    lang: str,
    openai_api_key: str = '',
) -> tuple[list[Chapter], bool]:
    logger.info(
        f'summarize, '
        f'vid={vid}, '
        f'len(chapters)={len(chapters)}, '
        f'len(timed_texts)={len(timed_texts)}, '
        f'lang={lang}')

    chapters: list[Chapter] = _parse_chapters(
        vid=vid,
        trigger=trigger,
        chapters=chapters,
        lang=lang,
    )
    if not chapters:
        chapters = await _generate_chapters(
            vid=vid,
            trigger=trigger,
            timed_texts=timed_texts,
            lang=lang,
            openai_api_key=openai_api_key,
        )
        if not chapters:
            abort(500, f'summarize failed, no chapters, vid={vid}')
    else:
        data = build_summary_response(SummaryState.DOING, chapters)
        await sse_publish(channel=vid, event=SseEvent.SUMMARY, data=data)

    tasks = []
    for i, c in enumerate(chapters):
        start_time = c.seconds
        end_time = chapters[i + 1].seconds if i + 1 < len(chapters) else maxsize  # nopep8.
        texts = _get_timed_texts_in_range(
            timed_texts=timed_texts,
            start_time=start_time,
            end_time=end_time,
        )
        tasks.append(_summarize_chapter(
            chapter=c,
            timed_texts=texts,
            openai_api_key=openai_api_key,
        ))

    res = await asyncio.gather(*tasks, return_exceptions=True)
    has_exception = False

    for r in res:
        if isinstance(r, Exception):
            logger.error(f'summarize, but has exception, vid={vid}, e={r}')
            has_exception = True

    data = build_summary_response(SummaryState.DONE, chapters)
    await sse_publish(channel=vid, event=SseEvent.SUMMARY, data=data)
    await sse_publish(channel=vid, event=SseEvent.CLOSE)
    return chapters, has_exception


def _parse_chapters(
    vid: str,
    trigger: str,
    chapters: list[dict],
    lang: str,
) -> list[Chapter]:
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
                cid=str(uuid4()),
                vid=vid,
                trigger=trigger,
                slicer=Slicer.YOUTUBE.value,
                seconds=seconds,
                lang=lang,
                chapter=c['title'],
            ))
    except Exception:
        logger.exception(f'parse chapters failed, vid={vid}')
        return res

    return res


async def _generate_chapters(
    vid: str,
    trigger: str,
    timed_texts: list[TimedText],
    lang: str,
    openai_api_key: str = '',
) -> list[Chapter]:
    chapters: list[Chapter] = []
    timed_texts_start = 0
    latest_end_at = -1

    while True:
        texts = timed_texts[timed_texts_start:]
        if not texts:
            logger.info(f'generate chapters, drained, '
                        f'vid={vid}, '
                        f'len={len(timed_texts)}, '
                        f'timed_texts_start={timed_texts_start}')
            break  # drained.

        content = ''
        start_time = int(texts[0].start)
        system_prompt = _GENERATE_CHAPTERS_SYSTEM_PROMPT.format(start_time=start_time)  # nopep8.
        system_message = build_message(Role.SYSTEM, system_prompt)

        for t in texts:
            text = t.text.strip()
            if not text:
                continue

            temp = {
                'index': timed_texts_start,
                'seconds': int(t.start),
                'text': text,
            }
            temp = json.dumps(temp, ensure_ascii=False)
            temp = content + '\n' + temp if content else temp
            user_message = build_message(Role.USER, temp)

            if count_tokens([system_message, user_message]) < _GENERATE_CHAPTERS_TOKEN_LIMIT:
                content = temp.strip()
                timed_texts_start += 1
            else:
                break  # for.

        logger.info(f'generate chapters, '
                    f'vid={vid}, '
                    f'timed_texts_start={timed_texts_start}, '
                    f'latest_end_at={latest_end_at}')

        user_message = build_message(Role.USER, content)
        body = await chat(
            messages=[system_message, user_message],
            model=Model.GPT_3_5_TURBO,
            top_p=0.1,
            timeout=90,
            api_key=openai_api_key,
        )
        content = get_content(body)
        logger.info(f'generate chapters, vid={vid}, content=\n{content}')

        res: dict = json.loads(content)
        chapter = res.get('chapter', '').strip()
        seconds = res.get('seconds', -1)
        end_at = res.get('end_at')

        # Looks like it's the end and meanless, so ignore the chapter.
        if type(end_at) is not int:  # NoneType.
            logger.info(f'generate chapters, end_at is not int, vid={vid}')
            break  # drained.

        if chapter and seconds >= 0:
            data = Chapter(
                cid=str(uuid4()),
                vid=vid,
                trigger=trigger,
                slicer=Slicer.OPENAI.value,
                seconds=seconds,
                lang=lang,
                chapter=chapter,
            )

            chapters.append(data)
            await sse_publish(
                channel=vid,
                event=SseEvent.SUMMARY,
                data=build_summary_response(SummaryState.DOING, chapters),
            )

        # Looks like it's the end and meanless, so ignore the chapter.
        # if type(end_at) is not int:  # NoneType.
        #     logger.info(f'generate chapters, end_at is not int, vid={vid}')
        #     break  # drained.

        if end_at <= latest_end_at:
            logger.warning(f'generate chapters, avoid infinite loop, vid={vid}')  # nopep8.
            latest_end_at += 5  # force a different context.
            timed_texts_start = latest_end_at
        elif end_at > timed_texts_start:
            logger.warning(f'generate chapters, avoid drain early, vid={vid}')
            latest_end_at = timed_texts_start
            timed_texts_start = latest_end_at + 1
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


async def _summarize_chapter(
    chapter: Chapter,
    timed_texts: list[TimedText],
    openai_api_key: str = '',
):
    summary = ''
    summary_start = 0
    refined_count = 0

    while True:
        texts = timed_texts[summary_start:]
        if not texts:
            break  # drained.

        content = ''
        content_has_changed = False

        for t in texts:
            lines = content + '\n' + t.text if content else t.text
            if refined_count <= 0:
                system_prompt = _SUMMARIZE_FIRST_CHAPTER_SYSTEM_PROMPT.format(
                    chapter=chapter.chapter,
                )
            else:
                system_prompt = _SUMMARIZE_NEXT_CHAPTER_SYSTEM_PROMPT.format(
                    chapter=chapter.chapter,
                    summary=summary,
                )

            system_message = build_message(Role.SYSTEM, system_prompt)
            user_message = build_message(Role.USER, lines)
            token_limit = _SUMMARIZE_FIRST_CHAPTER_TOKEN_LIMIT \
                if refined_count <= 0 else _SUMMARIZE_NEXT_CHAPTER_TOKEN_LIMIT

            if count_tokens([system_message, user_message]) < token_limit:
                content_has_changed = True
                content = lines.strip()
                summary_start += 1
            else:
                break  # for.

        # FIXME (Matthew Lee) it is possible that content not changed, simply avoid redundant requests.
        if not content_has_changed:
            logger.warning(f'summarize chapter, but content not changed, vid={chapter.vid}')  # nopep8.
            break

        if refined_count <= 0:
            system_prompt = _SUMMARIZE_FIRST_CHAPTER_SYSTEM_PROMPT.format(
                chapter=chapter.chapter,
            )
        else:
            system_prompt = _SUMMARIZE_NEXT_CHAPTER_SYSTEM_PROMPT.format(
                chapter=chapter.chapter,
                summary=summary,
            )

        system_message = build_message(Role.SYSTEM, system_prompt)
        user_message = build_message(Role.USER, content)
        body = await chat(
            messages=[system_message, user_message],
            model=Model.GPT_3_5_TURBO,
            top_p=0.1,
            timeout=90,
            api_key=openai_api_key,
        )

        summary = get_content(body).strip()
        chapter.summary = summary  # cache even not finished.
        refined_count += 1

    chapter.summary = summary.strip()
    chapter.refined = refined_count

    await sse_publish(
        channel=chapter.vid,
        event=SseEvent.SUMMARY,
        data=build_summary_response(SummaryState.DOING, [chapter]),
    )
