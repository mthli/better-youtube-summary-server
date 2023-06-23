import json

from quart import abort

from database.chapter import find_chapter_by_cid
from database.data import Translation
from database.translation import \
    find_translation, \
    insert_or_update_translation
from logger import logger
from openai import Model, Role, \
    build_message, \
    chat, \
    count_tokens, \
    get_content

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


async def translate(
    vid: str,
    cid: str,
    lang: str,
    openai_api_key: str = '',
) -> Translation:
    trans = find_translation(vid=vid, cid=cid, lang=lang)
    if trans and trans.chapter and trans.summary:
        return trans

    chapter = find_chapter_by_cid(cid)
    if not chapter:
        abort(404, f'translate, but chapter not found, vid={vid}, cid={cid}, lang={lang}')  # nopep8.

    system_prompt = _TRANSLATION_SYSTEM_PROMPT.format(lang=lang)
    system_message = build_message(Role.SYSTEM, system_prompt)
    user_message = build_message(Role.SYSTEM, json.dumps({
        'chapter': chapter.chapter,
        'summary': chapter.summary,
    }, ensure_ascii=False))

    # Don't check token limit here, let it go.
    messages = [system_message, user_message]
    tokens = count_tokens(messages)
    logger.info(f'translate, vid={vid}, cid={cid}, lang={lang}, tokens={tokens}')  # nopep8.

    body = await chat(
        messages=messages,
        model=Model.GPT_3_5_TURBO,
        top_p=0.1,
        timeout=90,
        api_key=openai_api_key,
    )

    content = get_content(body)
    logger.info(f'translate, vid={vid}, cid={cid}, lang={lang}, content=\n{content}')  # nopep8.

    # FIXME (Matthew Lee) prompt output as JSON may not work.
    res: dict = json.loads(content)
    chapter = res.get('chapter', '').strip()
    summary = res.get('summary', '').strip()

    # Both fields must exist.
    if (not chapter) or (not summary):
        abort(500, f'translate, but chapter or summary empty, vid={vid}, cid={cid}, lang={lang}')  # nopep8.

    trans = Translation(
        vid=vid,
        cid=cid,
        lang=lang,
        chapter=chapter,
        summary=summary,
    )

    insert_or_update_translation(trans)
    return trans
