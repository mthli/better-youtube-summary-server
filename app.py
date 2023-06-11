from dataclasses import asdict
from urllib.parse import urlparse, parse_qs

from flask import Flask, abort, json, request
from flask_sse import sse
from urlmatch import urlmatch
from werkzeug.exceptions import HTTPException

from constants import APPLICATION_JSON
from logger import logger
from summary import summarize as summarizing

app = Flask(__name__)
app.config['REDIS_URL'] = 'redis://localhost'
app.register_blueprint(sse, url_prefix='/api/sse')


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


# {
#   'page_url':  str,  required.
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

    page_url = _parse_page_url_from_body(body)
    timedtext = _parse_timedtext_from_body(body)
    chapters = _parse_chapters_from_body(body)
    language = _parse_language_from_body(body)

    query = urlparse(page_url).query
    vid = parse_qs(query).get('v', '') if query else ''
    if not vid:
        abort(400, f'vid not exists, page_url={page_url}')

    chapters = await summarizing(vid=vid, timedtext=timedtext, chapters=chapters)
    chapters = list(map(lambda c: asdict(c), chapters))

    return {
        'chapters': chapters,
    }


def _parse_page_url_from_body(body: dict) -> str:
    page_url = body.get('page_url', '')
    if not isinstance(page_url, str):
        abort(400, f'"page_url" must be string, page_url={page_url}')
    page_url = page_url.strip()
    if not urlmatch('https://*.youtube.com/watch*', page_url):
        abort(400, f'"page_url" not supported, page_url={page_url}')
    return page_url


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
