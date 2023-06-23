from dataclasses import asdict

from langcodes import Language

from database.data import Chapter, State, Translation
from database.translation import find_translation
from logger import logger
from sse import SseEvent, sse_publish


def build_translation_response(state: State, trans: list[Translation] = []) -> dict:
    trans = list(map(lambda c: asdict(c), trans))
    return {
        'state': state.value,
        'translation': trans,
    }


async def translate(vid: str, chapters: list[Chapter], language: Language):
    if not chapters:
        logger.warning(f'translate, but chapters are empty, vid={vid}')
        return

    lang = language.language
    if not lang:
        logger.warning(f'translate, but lang not exists, vid={vid}')
        return

    for c in chapters:
        trans = find_translation(vid=c.vid, cid=c.cid, lang=lang)
        if not trans:
            pass

        await sse_publish(
            channel=vid,
            event=SseEvent.TRANSLATION,
            data=build_translation_response(State.DOING, [trans]),
        )
