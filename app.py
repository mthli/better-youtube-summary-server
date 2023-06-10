from flask import Flask, abort, json, request
from urllib.parse import urlparse, parse_qs
from urlmatch import urlmatch
from werkzeug.exceptions import HTTPException

from constants import APPLICATION_JSON
from logger import logger

app = Flask(__name__)


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
#   'page_url': str, required.
#   'language': str, optional.
# }
@app.post('/api/summarize')
async def summarize():
    try:
        body: dict = request.get_json()
    except Exception as e:
        abort(400, f'summarize failed, e={e}')

    page_url = _parse_page_url_from_body(body)
    query = urlparse(page_url).query
    vid = parse_qs(query).get('v', '') if query else ''
    if not vid:
        abort(400, f'vid not exists, page_url={page_url}')

    # TODO


def _parse_page_url_from_body(body: dict) -> str:
    page_url = body.get('page_url', '')
    if not isinstance(page_url, str):
        abort(400, f'"page_url" must be string, page_url={page_url}')
    page_url = page_url.strip()
    if not urlmatch('https://*.youtube.com/watch*', page_url):
        abort(400, f'"page_url" not supported, page_url={page_url}')
    return page_url
