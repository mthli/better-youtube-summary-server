from dataclasses import dataclass

from bs4 import BeautifulSoup
from flask import abort


@dataclass
class TimedText:
    start: float = 0  # seconds; required.
    dur: float = 0    # seconds; required.
    text: str = ''    # required.


async def summarize(vid: str, timedtext: str, chapters: list[str] = [], lang: str = 'en'):
    timed_texts = _parse_timed_texts(vid, timedtext)
    # TODO


def _parse_timed_texts(vid: str, src: str) -> list[TimedText]:
    timed_texts: list[TimedText] = []
    soup = BeautifulSoup(src, 'lxml')

    transcript_el = soup.find('transcript')
    if not transcript_el:
        abort(404, f'transcript not found, vid={vid}')

    text_els = transcript_el.find_all('text')
    if not text_els:
        abort(404, f'transcript is empty, vid={vid}')

    for text_el in text_els:
        timed_texts.append(TimedText(
            start=text_el.attrs['start'],
            dur=text_el.attrs['dur'],
            text=text_el.text,
        ))

    if not timed_texts:
        abort(400, f'transcript format invalid, vid={vid}')

    return timed_texts
