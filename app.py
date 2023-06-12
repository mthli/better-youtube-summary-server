from dataclasses import asdict
from enum import unique

from quart import Quart, abort, json, request, make_response
from strenum import StrEnum
from werkzeug.exceptions import HTTPException

from constants import APPLICATION_JSON
from database import Chapter, \
    create_chapter_table, \
    find_chapters_by_vid, \
    insert_chapters, \
    delete_chapters_by_vid
from logger import logger
from rds import rds
from sse import SseEvent, sse_publish, sse_subscribe
from summary import summarize as summarizing


@unique
class State(StrEnum):
    PROCESSING = 'processing'
    FINISHED = 'finished'


app = Quart(__name__)
create_chapter_table()


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


@app.get('/api/sse')
async def sse():
    vid = _parse_vid_from_body(request.args.to_dict())

    chapters = find_chapters_by_vid(vid)
    if chapters:
        logger.info(f'sse, found chapters in database, vid={vid}')
        data = list(map(lambda c: asdict(c), chapters))
        await sse_publish(channel=vid, event=SseEvent.CHAPTERS, data=data)
        await sse_publish(channel=vid, event=SseEvent.CLOSE, data={})
        return _build_summarize_response(chapters, State.FINISHED)

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
#   'vid':       str,  required.
#   'timedtext': str,  required.
#   'chapters':  dict, optional.
# }
@app.post('/api/summarize')
async def summarize():
    try:
        body: dict = (await request.form).to_dict()
    except Exception as e:
        abort(400, f'summarize failed, e={e}')

    vid = _parse_vid_from_body(body)
    timedtext = _parse_timedtext_from_body(body)
    chapters = _parse_chapters_from_body(body)

    found = find_chapters_by_vid(vid)
    if found:
        logger.info(f'summarize, found chapters in database, vid={vid}')
        return _build_summarize_response(found, State.FINISHED)

    rds_key = f'summarize_{vid}'
    if rds.exists(rds_key):
        logger.info(f'summarize, but repeated, vid={vid}')
        rds.set(rds_key, 1, ex=300)  # expires in 5 mins.
        return _build_summarize_response([], State.PROCESSING)
    rds.set(rds_key, 1, ex=300)  # expires in 5 mins.

    chapters, has_exception = await summarizing(vid, timedtext, chapters)

    if not has_exception:
        logger.info(f'summarize, save chapters to database, vid={vid}')
        delete_chapters_by_vid(vid)
        insert_chapters(chapters)

    rds.delete(rds_key)
    return _build_summarize_response(chapters, State.FINISHED)


def _parse_vid_from_body(body: dict) -> str:
    vid = body.get('vid', '')
    if not isinstance(vid, str):
        abort(400, f'"vid" must be string, vid={vid}')
    vid = vid.strip()
    if not vid:
        abort(400, f'"vid" is empty')
    return vid


def _parse_timedtext_from_body(body: dict) -> str:
    timedtext = body.get('timedtext', '')
    if not isinstance(timedtext, str):
        abort(400, f'"timedtext" must be string')
    timedtext = timedtext.strip()
    if not timedtext:
        abort(400, f'"timedtext" is empty')
    return timedtext


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


def _build_summarize_response(chapters: list[Chapter], state: State) -> dict:
    chapters = list(map(lambda c: asdict(c), chapters))
    return {
        'chapters': chapters,
        'state': state.value,
    }
