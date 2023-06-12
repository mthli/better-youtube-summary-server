from dataclasses import asdict

from flask import Flask, Response, abort, json, request, url_for
from flask_sse import sse
from werkzeug.exceptions import HTTPException

from constants import APPLICATION_JSON
from database import create_chapter_table, \
    insert_chapters, \
    delete_chapters_by_vid
from logger import logger
from summary import summarize as summarizing

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

    logger.info(f"summarize, sse.stream={url_for('sse.stream', channel=vid)}")
    chapters, has_exception = await summarizing(vid=vid, timedtext=timedtext, chapters=chapters)
    chapters = list(map(lambda c: asdict(c), chapters))

    if not has_exception:
        logger.info(f'summarize, cache it, vid={vid}')
        delete_chapters_by_vid(vid)
        insert_chapters(chapters)

    return {
        'chapters': chapters,
    }


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
