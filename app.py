from dataclasses import asdict
from enum import unique

from flask import Flask, Response, abort, json, request, url_for
from flask_sse import sse
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
from summary import summarize as summarizing


@unique
class State(StrEnum):
    PROCESSING = 'processing'
    FINISHED = 'finished'


_SSE_URL_PREFIX = '/api/sse'

app = Flask(__name__)
app.config['REDIS_URL'] = 'redis://localhost:6379'
app.register_blueprint(sse, url_prefix=_SSE_URL_PREFIX)

create_chapter_table()


# https://flask.palletsprojects.com/en/2.2.x/errorhandling/#generic-exception-handler
#
# If no handler is registered,
# HTTPException subclasses show a generic message about their code,
# while other exceptions are converted to a generic "500 Internal Server Error".
@app.errorhandler(HTTPException)
def handle_exception(e):
    response = e.get_response()
    response.data = json.dumps({
        'code': e.code,
        'name': e.name,
        'description': e.description,
    })
    response.content_type = APPLICATION_JSON
    logger.error(f'errorhandler, data={response.data}')
    return response


# https://github.com/singingwolfboy/flask-sse/issues/3
@app.after_request
def add_nginx_sse_headers(response: Response):
    if _SSE_URL_PREFIX not in request.url:
        return response  # DO NOTHING.
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Cache-Control'] = 'no-cache'
    return response


# {
#   'vid':       str,  required.
#   'timedtext': str,  required.
#   'chapters':  dict, optional.
#   'language':  str,  optional.
# }
@app.post('/api/summarize')
async def summarize():
    try:
        body: dict = request.form.to_dict()
    except Exception as e:
        abort(400, f'summarize failed, e={e}')

    vid = _parse_vid_from_body(body)
    timedtext = _parse_timedtext_from_body(body)
    chapters = _parse_chapters_from_body(body)
    language = _parse_language_from_body(body)
    # TODO (Matthew Lee) translate.

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

    logger.info(f"summarize, sse.stream={url_for('sse.stream', channel=vid)}")
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


def _parse_language_from_body(body: dict) -> str:
    language = body.get('language', '')
    if not isinstance(language, str):
        abort(400, f'"language" must be string')
    language = language.strip()
    return language if language else 'en'


def _build_summarize_response(chapters: list[Chapter], state: State) -> dict:
    chapters = list(map(lambda c: asdict(c), chapters))
    return {
        'chapters': chapters,
        'state': state.value,
    }
