from dataclasses import asdict
from uuid import uuid4

from arq import create_pool
from arq.connections import RedisSettings
from arq.typing import WorkerSettingsBase
from langcodes import Language
from quart import Quart, Response, abort, json, request, make_response
from werkzeug.datastructures import Headers
from werkzeug.exceptions import HTTPException
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled

from constants import APPLICATION_JSON
from database.chapter import \
    create_chapter_table, \
    find_chapters_by_vid, \
    insert_chapters, \
    delete_chapters_by_vid
from database.data import \
    Chapter, \
    ChapterSlicer, \
    Feedback, \
    State, \
    TimedText, \
    User
from database.feedback import \
    create_feedback_table, \
    find_feedback, \
    insert_or_update_feedback, \
    delete_feedback
from database.translation import create_translation_table, delete_translation
from database.user import create_user_table, find_user, insert_or_update_user
from logger import logger
from rds import rds
from sse import sse_subscribe
from summary import \
    SUMMARIZING_RDS_KEY_EX, \
    NO_TRANSCRIPT_RDS_KEY_EX, \
    build_summary_channel, \
    build_summary_response, \
    build_summarizing_rds_key, \
    build_no_transcript_rds_key, \
    do_if_found_chapters_in_database, \
    need_to_resummarize, \
    parse_timed_texts_and_lang, \
    summarize as summarizing
from translation import translate as translating

app = Quart(__name__)
create_chapter_table()
create_feedback_table()
create_translation_table()
create_user_table()


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


@app.post('/api/user')
async def add_user():
    uid = str(uuid4())
    insert_or_update_user(User(uid=uid))
    return {
        'uid': uid,
    }


# {
#   'vid':   str, required.
#   'bad':  bool, optional.
#   'good': bool, optional.
# }
@app.post('/api/feedback/<string:vid>')
async def feedback(vid: str):
    try:
        body: dict = await request.get_json() or {}
    except Exception as e:
        abort(400, f'feedback failed, e={e}')

    _ = _parse_uid_from_headers(request.headers)

    found = find_chapters_by_vid(vid=vid, limit=1)
    if not found:
        return {}

    feedback = find_feedback(vid)
    if not feedback:
        feedback = Feedback(vid=vid)

    good = body.get('good', False)
    if not isinstance(good, bool):
        abort(400, '"good" must be bool')
    if good:
        feedback.good += 1

    bad = body.get('bad', False)
    if not isinstance(bad, bool):
        abort(400, '"bad" must be bool')
    if bad:
        feedback.bad += 1

    insert_or_update_feedback(feedback)
    return {}


# {
#   'chapters': dict, optional.
#   'no_transcript': boolean, optional.
# }
@app.post('/api/summarize/<string:vid>')
async def summarize(vid: str):
    try:
        body: dict = await request.get_json() or {}
    except Exception as e:
        abort(400, f'summarize failed, e={e}')

    uid = _parse_uid_from_headers(request.headers)
    openai_api_key = _parse_openai_api_key_from_headers(request.headers)
    chapters = _parse_chapters_from_body(body)
    no_transcript = bool(body.get('no_transcript', False))

    no_transcript_rds_key = build_no_transcript_rds_key(vid)
    summarizing_rds_key = build_summarizing_rds_key(vid)
    channel = build_summary_channel(vid)

    found = find_chapters_by_vid(vid)
    if found:
        if (chapters and found[0].slicer != ChapterSlicer.YOUTUBE) or \
                need_to_resummarize(vid, found):
            logger.info(f'summarize, need to resummarize, vid={vid}')
            delete_chapters_by_vid(vid)
            delete_feedback(vid)
            delete_translation(vid)
            rds.delete(no_transcript_rds_key)
            rds.delete(summarizing_rds_key)
        else:
            logger.info(f'summarize, found chapters in database, vid={vid}')
            await do_if_found_chapters_in_database(vid, found)
            return build_summary_response(State.DONE, found)

    if rds.exists(no_transcript_rds_key) or no_transcript:
        logger.info(f'summarize, but no transcript for now, vid={vid}')
        return build_summary_response(State.NOTHING)

    if rds.exists(summarizing_rds_key):
        logger.info(f'summarize, but repeated, vid={vid}')
        return await _build_sse_response(channel)

    # Set the summary proccess beginning flag here,
    # because of we need to get the transcript first,
    # and try to avoid youtube rate limits.
    rds.set(summarizing_rds_key, 1, ex=SUMMARIZING_RDS_KEY_EX)

    try:
        # FIXME (Matthew Lee) youtube rate limits?
        timed_texts, lang = parse_timed_texts_and_lang(vid)
        if not timed_texts:
            logger.warning(f'summarize, but no transcript found, vid={vid}')
            rds.set(no_transcript_rds_key, 1, ex=NO_TRANSCRIPT_RDS_KEY_EX)
            rds.delete(summarizing_rds_key)
            return build_summary_response(State.NOTHING)
    except (NoTranscriptFound, TranscriptsDisabled):
        logger.warning(f'summarize, but no transcript found, vid={vid}')
        rds.set(no_transcript_rds_key, 1, ex=NO_TRANSCRIPT_RDS_KEY_EX)
        rds.delete(summarizing_rds_key)
        return build_summary_response(State.NOTHING)
    except Exception:
        logger.exception(f'summarize failed, vid={vid}')
        rds.delete(no_transcript_rds_key)
        rds.delete(summarizing_rds_key)
        raise  # to errorhandler.

    await app.arq.enqueue_job(
        do_summarize_job.__name__,
        vid,
        uid,
        chapters,
        timed_texts,
        lang,
        openai_api_key,
    )

    return await _build_sse_response(channel)


# {
#   'cid':  str, required.
#   'lang': str, required.
# }
@app.post('/api/translate/<string:vid>')
async def translate(vid: str):
    _ = _parse_uid_from_headers(request.headers)
    openai_api_key = _parse_openai_api_key_from_headers(request.headers)

    try:
        body: dict = await request.get_json() or {}
    except Exception as e:
        abort(400, f'translate failed, e={e}')

    cid = body.get('cid', '')
    if not isinstance(cid, str):
        abort(400, f'"cid" must be string')
    cid = cid.strip()
    if not cid:
        abort(400, f'"cid" must not empty')

    lang = body.get('lang', '')
    if not isinstance(lang, str):
        abort(400, f'"lang" must be string')
    lang = lang.strip()
    if not lang:
        abort(400, f'"lang" must not empty')
    lang = Language.get(lang)  # LanguageTagError.
    if not lang.is_valid():
        abort(400, f'"lang" invalid')
    lang = lang.language  # to str.

    trans = await translating(
        vid=vid,
        cid=cid,
        lang=lang,
        openai_api_key=openai_api_key,
    )

    return asdict(trans)


def _parse_uid_from_headers(headers: Headers, check: bool = True) -> str:
    uid = headers.get(key='uid', default='', type=str)
    if not isinstance(uid, str):
        abort(400, f'"uid" must be string')

    uid = uid.strip()
    if not uid:
        abort(400, f'"uid" must not empty')

    if check:
        user = find_user(uid=uid)
        if not user:
            abort(404, f'user not exists')
        if user.is_deleted:
            abort(404, f'user is deleted')

    return uid


def _parse_openai_api_key_from_headers(headers: Headers) -> str:
    # Don't use underscore here because of Ngnix.
    openai_api_key = headers.get(key='openai-api-key', default='', type=str)
    if not isinstance(openai_api_key, str):
        abort(400, f'"openai-api-key" must be string')
    return openai_api_key.strip()


def _parse_chapters_from_body(body: dict) -> list[dict]:
    chapters = body.get('chapters', [])
    if not isinstance(chapters, list):
        abort(400, f'"chapters" must be list')
    for c in chapters:
        if not isinstance(c, dict):
            abort(400, f'"chapters" item must be dict')
    return chapters


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
    trigger: str,
    chapters: list[dict],
    timed_texts: list[TimedText],
    lang: str,
    openai_api_key: str = '',
):
    logger.info(f'do summarize job, vid={vid}')

    # Set flag again, although we have done this before.
    summarizing_rds_key = build_summarizing_rds_key(vid)
    rds.set(summarizing_rds_key, 1, ex=SUMMARIZING_RDS_KEY_EX)

    chapters, _ = await summarizing(
        vid=vid,
        trigger=trigger,
        chapters=chapters,
        timed_texts=timed_texts,
        lang=lang,
        openai_api_key=openai_api_key,
    )

    if chapters:
        logger.info(f'summarize, save chapters to database, vid={vid}')
        delete_chapters_by_vid(vid)
        delete_feedback(vid)
        delete_translation(vid)
        insert_chapters(chapters)

    rds.delete(build_no_transcript_rds_key(vid))
    rds.delete(summarizing_rds_key)


# https://quart.palletsprojects.com/en/latest/how_to_guides/server_sent_events.html
async def _build_sse_response(channel: str) -> Response:
    res = await make_response(
        sse_subscribe(channel),
        {
            'Content-Type': 'text/event-stream',
            'Transfer-Encoding': 'chunked',
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )

    res.timeout = None
    return res


# https://arq-docs.helpmanual.io/#simple-usage
class WorkerSettings(WorkerSettingsBase):
    functions = [do_summarize_job]
    on_startup = do_on_arq_worker_startup
    on_shutdown = do_on_arq_worker_shutdown
