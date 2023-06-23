import asyncio
import json

from dataclasses import asdict

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

TRANSLATING_RDS_KEY_EX = 300  # 5 mins.


def build_translation_channel(vid: str, lang: str) -> str:
    return f'translation_channel_{vid}_{lang}'


def build_translation_response(state: State, trans: list[Translation] = []) -> dict:
    trans = list(map(lambda c: asdict(c), trans))
    return {
        'state': state.value,
        'translation': trans,
    }


def build_translating_rds_key(vid: str, lang: str) -> str:
    return f'translating_{vid}_{lang}'


async def translate(
    vid: str,
    chapters: list[Chapter],
    lang: str,
    openai_api_key: str = '',
):
    if not chapters:
        logger.warning(f'translate, but chapters are empty, vid={vid}')
        return

    if not lang:
        logger.warning(f'translate, but lang not exists, vid={vid}')
        return

    tasks = []
    for c in chapters:
        tasks.append(_translate_chapter(
            chapter=c,
            lang=lang,
            openai_api_key=openai_api_key,
        ))

    res = await asyncio.gather(*tasks, return_exceptions=True)
    trans: list[Translation] = []

    for r in res:
        if isinstance(r, Translation):
            trans.append(r)
        elif isinstance(r, Exception):
            logger.error(f'translate, but has exception, vid={vid}, e={r}')

    channel = build_translation_channel(vid, lang)
    data = build_translation_response(State.DONE, trans)
    await sse_publish(channel=channel, event=SseEvent.TRANSLATION, data=data)
    await sse_publish(channel=channel, event=SseEvent.CLOSE)


async def _translate_chapter(
    chapter: Chapter,
    lang: str,
    openai_api_key: str = '',
) -> Translation:
    vid = chapter.vid
    cid = chapter.cid
    channel = build_translation_channel(vid, lang)

    found = find_translation(vid=vid, cid=cid, lang=lang)
    if found and found.chapter and found.summary:
        await sse_publish(
            channel=channel,
            event=SseEvent.TRANSLATION,
            data=build_translation_response(State.DOING, [found]),
        )
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
    await sse_publish(
        channel=channel,
        event=SseEvent.TRANSLATION,
        data=build_translation_response(State.DOING, [trans]),
    )

    return trans
