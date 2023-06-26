import asyncio
import json

from dataclasses import asdict
from sys import maxsize
from uuid import uuid4

from quart import abort
from youtube_transcript_api import YouTubeTranscriptApi

from database.data import \
    Chapter, \
    ChapterSlicer, \
    ChapterStyle, \
    State, \
    TimedText
from database.feedback import find_feedback
from logger import logger
from openai import Model, Role, \
    build_message, \
    chat, \
    count_tokens, \
    get_content
from prompt import \
    GENERATE_MULTI_CHAPTERS_TOKEN_LIMIT_FOR_4K, \
    GENERATE_MULTI_CHAPTERS_TOKEN_LIMIT_FOR_16K, \
    GENERATE_ONE_CHAPTER_SYSTEM_PROMPT, \
    GENERATE_ONE_CHAPTER_TOKEN_LIMIT, \
    SUMMARIZE_FIRST_CHAPTER_SYSTEM_PROMPT, \
    SUMMARIZE_FIRST_CHAPTER_TOKEN_LIMIT, \
    SUMMARIZE_NEXT_CHAPTER_SYSTEM_PROMPT, \
    SUMMARIZE_NEXT_CHAPTER_TOKEN_LIMIT, \
    generate_multi_chapters_example_messages_for_4k, \
    generate_multi_chapters_example_messages_for_16k
from rds import rds
from sse import SseEvent, sse_publish

SUMMARIZING_RDS_KEY_EX = 300  # 5 mins.
NO_TRANSCRIPT_RDS_KEY_EX = 8 * 60 * 60  # 8 hours.


def build_summary_channel(vid: str) -> str:
    return f'summary_{vid}'


def build_summary_response(state: State, chapters: list[Chapter] = []) -> dict:
    chapters = list(map(lambda c: asdict(c), chapters))
    return {
        'state': state.value,
        'chapters': chapters,
    }


def build_summarizing_rds_key(vid: str) -> str:
    return f'summarizing_{vid}'


def build_no_transcript_rds_key(vid: str) -> str:
    return f'no_transcript_{vid}'


async def do_if_found_chapters_in_database(vid: str, chapters: list[Chapter]):
    rds.delete(build_no_transcript_rds_key(vid))
    rds.delete(build_summarizing_rds_key(vid))
    channel = build_summary_channel(vid)
    data = build_summary_response(State.DONE, chapters)
    await sse_publish(channel=channel, event=SseEvent.SUMMARY, data=data)
    await sse_publish(channel=channel, event=SseEvent.CLOSE)


def need_to_resummarize(vid: str, chapters: list[Chapter] = []) -> bool:
    for c in chapters:
        if (not c.summary) or len(c.summary) <= 0:
            return True

    feedback = find_feedback(vid)
    if not feedback:
        return False

    good = feedback.good if feedback.good > 0 else 1
    bad = feedback.bad if feedback.bad > 0 else 1

    # DO NOTHING if total less then 10.
    if good + bad < 10:
        return False

    # Need to resummarize if bad percent >= 20%
    return bad / (good + bad) >= 0.2


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
        'zh-CN',  # Chinese (China).
        'zh-HK',  # Chinese (Hong Kong).
        'zh-TW',  # Chinese (Taiwan).
        'zh',  # Chinese.
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

    has_exception = False
    chapters: list[Chapter] = _parse_chapters(
        vid=vid,
        trigger=trigger,
        chapters=chapters,
        lang=lang,
    )

    if not chapters:
        # Use the "outline" and "information" fields if they can be generated in 4k.
        chapters = await _generate_multi_chapters(
            vid=vid,
            trigger=trigger,
            timed_texts=timed_texts,
            lang=lang,
            model=Model.GPT_3_5_TURBO,
            openai_api_key=openai_api_key,
        )
        if chapters:
            await _do_before_return(vid, chapters)
            return chapters, has_exception

        # Just use the "outline" field if it can be generated in 16k.
        chapters = await _generate_multi_chapters(
            vid=vid,
            trigger=trigger,
            timed_texts=timed_texts,
            lang=lang,
            model=Model.GPT_3_5_TURBO_16K,
            openai_api_key=openai_api_key,
        )

        if not chapters:
            chapters = await _generate_chapters_one_by_one(
                vid=vid,
                trigger=trigger,
                timed_texts=timed_texts,
                lang=lang,
                openai_api_key=openai_api_key,
            )

        if not chapters:
            abort(500, f'summarize failed, no chapters, vid={vid}')
    else:
        await sse_publish(
            channel=build_summary_channel(vid),
            event=SseEvent.SUMMARY,
            data=build_summary_response(State.DOING, chapters),
        )

    tasks = []
    for i, c in enumerate(chapters):
        start_time = c.start
        end_time = chapters[i + 1].start if i + 1 < len(chapters) else maxsize  # nopep8.
        texts = _get_timed_texts_in_range(
            timed_texts=timed_texts,
            start_time=start_time,
            end_time=end_time,
        )
        tasks.append(_summarize_chapter(
            chapter=c,
            timed_texts=texts,
            lang=lang,
            openai_api_key=openai_api_key,
        ))

    res = await asyncio.gather(*tasks, return_exceptions=True)
    for r in res:
        if isinstance(r, Exception):
            logger.error(f'summarize, but has exception, vid={vid}, e={r}')
            has_exception = True

    await _do_before_return(vid, chapters)
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
                slicer=ChapterSlicer.YOUTUBE.value,
                style=ChapterStyle.MARKDOWN.value,
                start=seconds,
                lang=lang,
                chapter=c['title'],
            ))
    except Exception:
        logger.exception(f'parse chapters failed, vid={vid}')
        return res

    return res


# FIXME (Matthew Lee) suppurt stream.
async def _generate_multi_chapters(
    vid: str,
    trigger: str,
    timed_texts: list[TimedText],
    lang: str,
    model: Model = Model.GPT_3_5_TURBO,
    openai_api_key: str = '',
) -> list[Chapter]:
    chapters: list[Chapter] = []
    content: list[dict] = []

    for t in timed_texts:
        text = t.text.strip()
        if not text:
            continue
        content.append({
            'start': int(t.start),
            'text': text,
        })

    user_message = build_message(
        role=Role.USER,
        content=json.dumps(content, ensure_ascii=False),
    )

    if model == Model.GPT_3_5_TURBO:
        messages = generate_multi_chapters_example_messages_for_4k(lang=lang)
        messages.append(user_message)
        count = count_tokens(messages)
        if count >= GENERATE_MULTI_CHAPTERS_TOKEN_LIMIT_FOR_4K:
            logger.info(f'generate multi chapters with 4k, reach token limit, vid={vid}, count={count}')  # nopep8.
            return chapters
    elif model == Model.GPT_3_5_TURBO_16K:
        messages = generate_multi_chapters_example_messages_for_16k(lang=lang)
        messages.append(user_message)
        count = count_tokens(messages)
        if count >= GENERATE_MULTI_CHAPTERS_TOKEN_LIMIT_FOR_16K:
            logger.info(f'generate multi chapters with 16k, reach token limit, vid={vid}, count={count}')  # nopep8.
            return chapters
    else:
        abort(500, f'generate multi chapters with wrong model, model={model}')

    try:
        body = await chat(
            messages=messages,
            model=model,
            top_p=0.1,
            timeout=90,
            api_key=openai_api_key,
        )

        content = get_content(body)
        logger.info(f'generate multi chapters, vid={vid}, content=\n{content}')

        # FIXME (Matthew Lee) prompt output as JSON may not work (in the end).
        res: list[dict] = json.loads(content)
    except Exception:
        logger.exception(f'generate multi chapters failed, vid={vid}')
        return chapters

    for r in res:
        chapter = r.get('outline', '').strip()
        information = r.get('information', '').strip()
        seconds = r.get('start', -1)

        if chapter and information and seconds >= 0:
            chapters.append(Chapter(
                cid=str(uuid4()),
                vid=vid,
                trigger=trigger,
                slicer=ChapterSlicer.OPENAI.value,
                style=ChapterStyle.TEXT.value,
                start=seconds,
                lang=lang,
                chapter=chapter,
                summary=information,
            ))

    # FIXME (Matthew Lee) prompt output may not sortd by seconds asc.
    return sorted(chapters, key=lambda c: c.start)


async def _generate_chapters_one_by_one(
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
            logger.info(f'generate one chapter, drained, '
                        f'vid={vid}, '
                        f'len={len(timed_texts)}, '
                        f'timed_texts_start={timed_texts_start}')
            break  # drained.

        system_prompt = GENERATE_ONE_CHAPTER_SYSTEM_PROMPT.format(
            start_time=int(texts[0].start),
            lang=lang,
        )
        system_message = build_message(Role.SYSTEM, system_prompt)

        content: list[dict] = []
        for t in texts:
            text = t.text.strip()
            if not text:
                continue

            temp = content.copy()
            temp.append({
                'index': timed_texts_start,
                'start': int(t.start),
                'text': text,
            })

            user_message = build_message(
                role=Role.USER,
                content=json.dumps(temp, ensure_ascii=False),
            )

            if count_tokens([system_message, user_message]) < GENERATE_ONE_CHAPTER_TOKEN_LIMIT:
                content = temp
                timed_texts_start += 1
            else:
                break  # for.

        user_message = build_message(
            role=Role.USER,
            content=json.dumps(content, ensure_ascii=False),
        )

        logger.info(f'generate one chapter, '
                    f'vid={vid}, '
                    f'latest_end_at={latest_end_at}, '
                    f'timed_texts_start={timed_texts_start}')

        try:
            body = await chat(
                messages=[system_message, user_message],
                model=Model.GPT_3_5_TURBO,
                top_p=0.1,
                timeout=90,
                api_key=openai_api_key,
            )

            content = get_content(body)
            logger.info(f'generate one chapter, vid={vid}, content=\n{content}')  # nopep8.

            # FIXME (Matthew Lee) prompt output as JSON may not work (in the end).
            res: dict = json.loads(content)
        except Exception:
            logger.exception(f'generate one chapter failed, vid={vid}')
            break  # drained.

        chapter = res.get('outline', '').strip()
        seconds = res.get('start', -1)
        end_at = res.get('end_at')

        # Looks like it's the end and meanless, so ignore the chapter.
        if type(end_at) is not int:  # NoneType.
            logger.info(f'generate one chapter, end_at is not int, vid={vid}')
            break  # drained.

        if chapter and seconds >= 0:
            data = Chapter(
                cid=str(uuid4()),
                vid=vid,
                trigger=trigger,
                slicer=ChapterSlicer.OPENAI.value,
                style=ChapterStyle.MARKDOWN.value,
                start=seconds,
                lang=lang,
                chapter=chapter,
            )

            chapters.append(data)
            await sse_publish(
                channel=build_summary_channel(vid),
                event=SseEvent.SUMMARY,
                data=build_summary_response(State.DOING, chapters),
            )

        # Looks like it's the end and meanless, so ignore the chapter.
        # if type(end_at) is not int:  # NoneType.
        #     logger.info(f'generate chapters, end_at is not int, vid={vid}')
        #     break  # drained.

        if end_at <= latest_end_at:
            logger.warning(f'generate one chapter, avoid infinite loop, vid={vid}')  # nopep8.
            latest_end_at += 5  # force a different context.
            timed_texts_start = latest_end_at
        elif end_at > timed_texts_start:
            logger.warning(f'generate one chapter, avoid drain early, vid={vid}')  # nopep8.
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
    lang: str,
    openai_api_key: str = '',
):
    vid = chapter.vid
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
            lines = content + '\n' + f'[{t.text}]' if content else f'[{t.text}]'  # nopep8.
            if refined_count <= 0:
                system_prompt = SUMMARIZE_FIRST_CHAPTER_SYSTEM_PROMPT.format(
                    chapter=chapter.chapter,
                    lang=lang,
                )
            else:
                system_prompt = SUMMARIZE_NEXT_CHAPTER_SYSTEM_PROMPT.format(
                    chapter=chapter.chapter,
                    summary=summary,
                    lang=lang,
                )

            system_message = build_message(Role.SYSTEM, system_prompt)
            user_message = build_message(Role.USER, lines)
            token_limit = SUMMARIZE_FIRST_CHAPTER_TOKEN_LIMIT \
                if refined_count <= 0 else SUMMARIZE_NEXT_CHAPTER_TOKEN_LIMIT

            if count_tokens([system_message, user_message]) < token_limit:
                content_has_changed = True
                content = lines.strip()
                summary_start += 1
            else:
                break  # for.

        # FIXME (Matthew Lee) it is possible that content not changed, simply avoid redundant requests.
        if not content_has_changed:
            logger.warning(f'summarize chapter, but content not changed, vid={vid}')  # nopep8.
            break

        if refined_count <= 0:
            system_prompt = SUMMARIZE_FIRST_CHAPTER_SYSTEM_PROMPT.format(
                chapter=chapter.chapter,
                lang=lang,
            )
        else:
            system_prompt = SUMMARIZE_NEXT_CHAPTER_SYSTEM_PROMPT.format(
                chapter=chapter.chapter,
                summary=summary,
                lang=lang,
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
    chapter.refined = refined_count - 1 if refined_count > 0 else 0

    await sse_publish(
        channel=build_summary_channel(vid),
        event=SseEvent.SUMMARY,
        data=build_summary_response(State.DOING, [chapter]),
    )


async def _do_before_return(vid: str, chapters: list[Chapter]):
    channel = build_summary_channel(vid)
    data = build_summary_response(State.DONE, chapters)
    await sse_publish(channel=channel, event=SseEvent.SUMMARY, data=data)
    await sse_publish(channel=channel, event=SseEvent.CLOSE)
