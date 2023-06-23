import asyncio
import json

from dataclasses import asdict

from langcodes import Language

from database.data import Chapter, State, Translation
from database.translation import \
    find_translation, \
    insert_or_update_translation
from logger import logger
from openai import Model, Role, \
    build_message, \
    chat, \
    count_tokens, \
    get_content
from sse import SseEvent, sse_publish

_TRANSLATION_SYSTEM_PROMPT = '''
Given the following JSON object as shown below:

```json
{{
  "chapter": "text...",
  "summary": "text..."
}}
```

Translate the "chapter" field and "summary" field to language {lang} in BCP 47,
the translation should keep the same format as the original field.

Do not output any redundant explanation other than JSON.
'''


def build_translation_channel(vid: str) -> str:
    return f'translation_channel_{vid}'


def build_translation_response(state: State, trans: list[Translation] = []) -> dict:
    trans = list(map(lambda c: asdict(c), trans))
    return {
        'state': state.value,
        'translation': trans,
    }


async def translate(
    vid: str,
    chapters: list[Chapter],
    language: Language,
    openai_api_key: str = '',
) -> tuple[list[Translation], bool]:
    trans: list[Translation] = []
    has_exception = False

    if not chapters:
        logger.warning(f'translate, but chapters are empty, vid={vid}')
        return trans, has_exception

    lang = language.language
    if not lang:
        logger.warning(f'translate, but lang not exists, vid={vid}')
        return trans, has_exception

    tasks = []
    for c in chapters:
        tasks.append(_translate_chapter(
            chapter=c,
            lang=lang,
            openai_api_key=openai_api_key,
        ))

    res = await asyncio.gather(*tasks, return_exceptions=True)
    for r in res:
        if isinstance(r, Translation):
            trans.append(r)
        elif isinstance(r, Exception):
            logger.error(f'translate, but has exception, vid={vid}, e={r}')
            has_exception = True

    await _do_sse_publish(State.DONE, trans)
    await sse_publish(
        channel=build_translation_channel(vid),
        event=SseEvent.CLOSE,
    )

    return trans, has_exception


async def _translate_chapter(
    chapter: Chapter,
    lang: str,
    openai_api_key: str = '',
) -> Translation:
    vid = chapter.vid
    cid = chapter.cid

    found = find_translation(vid=vid, cid=cid, lang=lang)
    if found and found.chapter and found.summary:
        await _do_sse_publish(State.DOING, [found])
        return found

    system_prompt = _TRANSLATION_SYSTEM_PROMPT.format(lang=lang)
    system_message = build_message(Role.SYSTEM, system_prompt)
    user_message = build_message(Role.SYSTEM, json.dumps({
        'chapter': chapter.chapter,
        'summary': chapter.summary,
    }, ensure_ascii=False))

    # Don't check token limit here, let it go.
    messages = [system_message, user_message]
    tokens = count_tokens(messages)
    logger.info(f'translate chapter, vid={vid}, tokens={tokens}')

    body = await chat(
        messages=messages,
        model=Model.GPT_3_5_TURBO,
        top_p=0.1,
        timeout=90,
        api_key=openai_api_key,
    )

    content = get_content(body)
    logger.info(f'translate chapter, vid={vid}, content=\n{content}')

    # FIXME (Matthew Lee) prompt output as JSON may not work.
    try:
        res: dict = json.loads(content)
    except Exception:
        logger.warning(f'translate chapter, json loads failed, vid={vid}')
        res = {}

    chapter = res.get('chapter', '').strip()
    summary = res.get('summary', '').strip()

    # Both fields must exist.
    # if (not chapter) or (not summary):
    #     return None

    trans = Translation(
        vid=vid,
        cid=cid,
        lang=lang,
        chapter=chapter,
        summary=summary,
    )

    insert_or_update_translation(trans)
    await _do_sse_publish(State.DOING, [trans])
    return trans


async def _do_sse_publish(state: State, trans: list[Translation]):
    await sse_publish(
        channel=build_translation_channel(trans.vid),
        event=SseEvent.TRANSLATION,
        data=build_translation_response(state, trans),
    )
