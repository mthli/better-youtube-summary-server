from dataclasses import asdict
from enum import unique

from arq import create_pool
from arq.connections import RedisSettings
from arq.typing import WorkerSettingsBase
from quart import Quart, abort, json, request, make_response
from strenum import StrEnum
from werkzeug.exceptions import HTTPException
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled

from constants import APPLICATION_JSON
from data import Chapter, Slicer
from database import \
    create_chapter_table, \
    find_chapters_by_vid, \
    insert_chapters, \
    delete_chapters_by_vid
from logger import logger
from rds import rds
from sse import SseEvent, sse_publish, sse_subscribe
from summary import TimedText, \
    parse_timed_texts_and_lang, \
    summarize as summarizing


@unique
class State(StrEnum):
    NOTHING = 'nothing'
    DOING = 'doing'
    DONE = 'done'


_SUMMARIZE_RDS_KEY_EX = 300  # 5 mins.
_NO_TRANSCRIPT_RDS_KEY_EX = 86400  # 24 hours.

app = Quart(__name__)
create_chapter_table()


# https://pgjones.gitlab.io/quart/how_to_guides/startup_shutdown.html
@app.before_serving
async def before_serving():
    logger.info(f'create arq in app before serving')
    app.arq = await create_pool(RedisSettings())


# https://flask.palletsprojects.com/en/2.2.x/errorhandling/#generic-exception-handler
#
# If no handler is registered,
# HTTPException subclasses show a generic message about their code,
# while other exceptions are converted to a generic "500 Internal Server Error".
@app.errorhandler(HTTPException)
def handle_exception(e: HTTPException):
    response = e.get_response()
    response.data = json.dumps({
        'code': e.code,
        'name': e.name,
        'description': e.description,
    })
    response.content_type = APPLICATION_JSON
    logger.error(f'errorhandler, data={response.data}')
    return response


@app.get('/api/sse/<string:vid>')
async def sse(vid: str):
    found = find_chapters_by_vid(vid)
    if found:
        logger.info(f'sse, found chapters in database, vid={vid}')
        await _do_if_found_chapters_in_database(vid, found)
        return _build_summarize_response(found, State.DONE)

    no_transcript_rds_key = _build_no_transcript_rds_key(vid)
    if rds.exists(no_transcript_rds_key):
        logger.info(f'sse, but no transcript for now, vid={vid}')
        return _build_summarize_response([], State.NOTHING)

    summarize_rds_key = _build_summarize_rds_key(vid)
    if not rds.exists(summarize_rds_key):
        logger.warning(f'sse, but no summarize process, vid={vid}')
        return _build_summarize_response([], State.NOTHING)

    # https://quart.palletsprojects.com/en/latest/how_to_guides/server_sent_events.html
    res = await make_response(
        sse_subscribe(vid),
        {
            'Content-Type': 'text/event-stream',
            'Transfer-Encoding': 'chunked',
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )

    res.timeout = None
    return res


# {
#   'chapters':  dict, optional.
#   'no_transcript': boolean, optional.
# }
@app.post('/api/summarize/<string:vid>')
async def summarize(vid: str):
    try:
        body: dict = await request.get_json()
    except Exception as e:
        abort(400, f'summarize failed, e={e}')

    chapters = _parse_chapters_from_body(body)
    no_transcript = bool(body.get('no_transcript', False))

    no_transcript_rds_key = _build_no_transcript_rds_key(vid)
    summarize_rds_key = _build_summarize_rds_key(vid)

    found = find_chapters_by_vid(vid)
    if found:
        if chapters and found[0].slicer != Slicer.YOUTUBE:
            logger.info(f'summarize, need to resummarize, vid={vid}')
            delete_chapters_by_vid(vid)        # 1 step.
            rds.delete(no_transcript_rds_key)  # 2 step.
            rds.delete(summarize_rds_key)      # 3 step.
        else:
            logger.info(f'summarize, found chapters in database, vid={vid}')
            await _do_if_found_chapters_in_database(vid, found)
            return _build_summarize_response(found, State.DONE)

    if rds.exists(no_transcript_rds_key) or no_transcript:
        logger.info(f'summarize, but no transcript for now, vid={vid}')
        return _build_summarize_response([], State.NOTHING)

    if rds.exists(summarize_rds_key):
        logger.info(f'summarize, but repeated, vid={vid}')
        rds.set(summarize_rds_key, 1, ex=_SUMMARIZE_RDS_KEY_EX)
        return _build_summarize_response([], State.DOING)

    # Set the summary proccess beginning flag here,
    # because of we need to get the transcript first,
    # and try to avoid youtube rate limits.
    rds.set(summarize_rds_key, 1, ex=_SUMMARIZE_RDS_KEY_EX)

    try:
        # FIXME (Matthew Lee) youtube rate limits?
        timed_texts, lang = parse_timed_texts_and_lang(vid)
        if not timed_texts:
            logger.warning(f'summarize, but no transcript found, vid={vid}')
            rds.set(no_transcript_rds_key, 1, ex=_NO_TRANSCRIPT_RDS_KEY_EX)
            rds.delete(summarize_rds_key)
            return _build_summarize_response([], State.NOTHING)
    except (NoTranscriptFound, TranscriptsDisabled):
        logger.warning(f'summarize, but no transcript found, vid={vid}')
        rds.set(no_transcript_rds_key, 1, ex=_NO_TRANSCRIPT_RDS_KEY_EX)
        rds.delete(summarize_rds_key)
        return _build_summarize_response([], State.NOTHING)
    except Exception:
        logger.exception(f'summarize failed, vid={vid}')
        rds.delete(no_transcript_rds_key)
        rds.delete(summarize_rds_key)
        raise  # to errorhandler.

    await app.arq.enqueue_job('do_summarize_job', vid, chapters, timed_texts, lang)
    return _build_summarize_response([], State.DOING)


def _parse_chapters_from_body(body: dict) -> list[dict]:
    chapters = body.get('chapters', [])
    if not isinstance(chapters, list):
        abort(400, f'"chapters" must be list')
    for c in chapters:
        if not isinstance(c, dict):
            abort(400, f'"chapters" item must be dict')
    return chapters


# def _parse_language_from_body(body: dict) -> str:
#     language = body.get('language', '')
#     if not isinstance(language, str):
#         abort(400, f'"language" must be string')
#     language = language.strip()
#     return language if language else 'en'


# ctx is arq first param, keep it.
async def do_on_arq_worker_startup(ctx: dict):
    logger.info(f'arq worker startup')


# ctx is arq first param, keep it.
async def do_on_arq_worker_shutdown(ctx: dict):
    logger.info(f'arq worker shutdown')


# ctx is arq first param, keep it.
async def do_summarize_job(
    ctx: dict,
    vid: str,
    chapters: list[dict],
    timed_texts: list[TimedText],
    lang: str,
):
    logger.info(f'do summarize job, vid={vid}')

    # Set flag again, although we have done this before.
    summarize_rds_key = _build_summarize_rds_key(vid)
    rds.set(summarize_rds_key, 1, ex=_SUMMARIZE_RDS_KEY_EX)

    chapters, has_exception = await summarizing(
        vid=vid,
        chapters=chapters,
        timed_texts=timed_texts,
        lang=lang,
    )

    if chapters and (not has_exception):
        logger.info(f'summarize, save chapters to database, vid={vid}')
        delete_chapters_by_vid(vid)
        insert_chapters(chapters)

    rds.delete(_build_no_transcript_rds_key(vid))
    rds.delete(summarize_rds_key)


def _build_summarize_rds_key(vid: str) -> str:
    return f'summarize_{vid}'


def _build_no_transcript_rds_key(vid: str) -> str:
    return f'no_transcript_{vid}'


def _build_summarize_response(chapters: list[Chapter], state: State) -> dict:
    chapters = list(map(lambda c: asdict(c), chapters))
    return {
        'chapters': chapters,
        'state': state.value,
    }


async def _do_if_found_chapters_in_database(vid: str, found: list[Chapter]):
    rds.delete(_build_no_transcript_rds_key(vid))
    rds.delete(_build_summarize_rds_key(vid))
    data = list(map(lambda c: asdict(c), found))
    await sse_publish(channel=vid, event=SseEvent.CHAPTERS, data=data)
    await sse_publish(channel=vid, event=SseEvent.CLOSE, data={})


# https://arq-docs.helpmanual.io/#simple-usage
class WorkerSettings(WorkerSettingsBase):
    functions = [do_summarize_job]
    on_startup = do_on_arq_worker_startup
    on_shutdown = do_on_arq_worker_shutdown
